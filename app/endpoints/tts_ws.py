import asyncio
import json
import logging
import time
import orjson
from fastapi import WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError
from typing import Dict, Optional

from ..tts.receive_text_from_frontend import receive_and_validate_text
from ..tts.text_to_audio import process_text_to_audio
from ..tts.send_audio_to_frontend import send_audio_to_frontend

logger = logging.getLogger("stefan-api-test-16")

# Global state för att hålla koll på pågående TTS-förfrågningar per WebSocket
active_tts_requests: Dict[WebSocket, asyncio.Task] = {}

async def _send_json(ws, obj: dict):
    """Skicka JSON (utf-8) till frontend."""
    try:
        await ws.send_text(orjson.dumps(obj).decode())
    except Exception:
        # Faller tillbaka till standardjson om orjson av någon anledning felar
        await ws.send_text(json.dumps(obj))

async def ws_tts(ws: WebSocket):
    await ws.accept()
    session_started_at = time.time()
    
    try:
        await _send_json(ws, {"type": "status", "stage": "ready"})
        logger.info("TTS WebSocket connection established")

        # Huvudloop för att hantera flera TTS-förfrågningar per anslutning
        while True:
            try:
                # Ta emot meddelande från klienten
                message = await ws.receive()
                
                # Hantera olika typer av meddelanden
                if message["type"] == "websocket.receive":
                    if "text" in message:
                        try:
                            data = orjson.loads(message["text"])
                        except Exception:
                            try:
                                data = json.loads(message["text"])
                            except Exception as e:
                                logger.error("Failed to parse JSON message: %s", e)
                                await _send_json(ws, {"type": "error", "message": "Invalid JSON format"})
                                continue
                        
                        # Hantera ping-meddelande för att hålla anslutningen vid liv
                        if data.get("type") == "ping":
                            await _send_json(ws, {"type": "pong"})
                            continue
                        
                        # Hantera TTS-förfrågan
                        if data.get("type") == "tts_request":
                            text = data.get("text", "").strip()
                            if not text:
                                await _send_json(ws, {"type": "error", "message": "No text provided"})
                                continue
                            
                            logger.info("🎤 New TTS request received: %s", text[:50] + "..." if len(text) > 50 else text)
                            logger.info("🔍 WebSocket state: %s, active_tts_requests keys: %s", 
                                       ws.client_state, list(active_tts_requests.keys()))
                            
                            # Avbryt pågående TTS-förfrågan om det finns en
                            if ws in active_tts_requests:
                                old_task = active_tts_requests[ws]
                                task_done = old_task.done() if old_task else "no_task"
                                logger.info("🔍 Found existing active task, task done: %s", task_done)
                                
                                if not old_task.done():
                                    logger.info("🛑 Cancelling previous TTS request to prioritize new one")
                                    old_task.cancel()
                                    # Vänta inte på att gamla task avslutas - starta ny direkt
                                else:
                                    logger.info("✅ Previous task was already done, cleaning up")
                                
                                del active_tts_requests[ws]
                                logger.info("🔍 Cleared old task, remaining active_tts_requests keys: %s", list(active_tts_requests.keys()))
                            else:
                                logger.info("✅ No existing active task found - channel is free")
                            
                            # Starta ny TTS-förfrågan som en task (utan att vänta)
                            task = asyncio.create_task(_process_tts_request(ws, text, session_started_at))
                            active_tts_requests[ws] = task
                            logger.info("🚀 Started new TTS task, active_tts_requests keys: %s", list(active_tts_requests.keys()))
                            
                            # Låt task köra i bakgrunden utan att blockera
                            # Detta gör att nya förfrågningar kan komma in snabbt
                        
                        # Hantera disconnect-förfrågan
                        elif data.get("type") == "disconnect":
                            logger.info("Client requested disconnect")
                            break
                        
                        # Hantera playback_complete-meddelande från frontend
                        elif data.get("type") == "playback_complete":
                            request_id = data.get("requestId")
                            logger.info("🎵 Received playback_complete for requestId: %s", request_id)
                            logger.info("🔍 WebSocket state: %s, active_tts_requests keys: %s", 
                                       ws.client_state, list(active_tts_requests.keys()))
                            
                            # RENSA active_tts_requests när playback är klar
                            if ws in active_tts_requests:
                                old_task = active_tts_requests[ws]
                                task_done = old_task.done() if old_task else "no_task"
                                logger.info("🔍 Found active task for this WebSocket, task done: %s", task_done)
                                
                                del active_tts_requests[ws]
                                logger.info("✅ Cleared active TTS request after playback_complete - channel is now free")
                                logger.info("🔍 Remaining active_tts_requests keys: %s", list(active_tts_requests.keys()))
                            else:
                                logger.warning("⚠️ No active TTS request found for this WebSocket in playback_complete")
                                logger.info("🔍 Current active_tts_requests keys: %s", list(active_tts_requests.keys()))
                            
                            await _send_json(ws, {"type": "status", "stage": "done"})
                            logger.info("📤 Sent 'done' status to frontend after playback_complete")
                        
                        else:
                            await _send_json(ws, {"type": "error", "message": f"Unknown message type: {data.get('type')}"})
                
                elif message["type"] == "websocket.disconnect":
                    logger.info("Client disconnected")
                    break
                    
            except WebSocketDisconnect:
                logger.info("Client disconnected")
                break
            except Exception as e:
                logger.error("Error processing message: %s", e)
                await _send_json(ws, {"type": "error", "message": str(e)})
                continue

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except (ConnectionClosedOK, ConnectionClosedError) as e:
        logger.info("Upstream WS closed: %s", e)
    except Exception as e:
        logger.exception("WS error: %s", e)
        try:
            await _send_json(ws, {"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        # Rensa upp active TTS requests för denna WebSocket
        if ws in active_tts_requests:
            old_task = active_tts_requests[ws]
            if not old_task.done():
                old_task.cancel()
                try:
                    await old_task
                except asyncio.CancelledError:
                    pass
            del active_tts_requests[ws]
        
        try:
            await ws.close()
        except Exception:
            pass
        logger.info("TTS WebSocket connection closed")


async def _process_tts_request(ws: WebSocket, text: str, session_started_at: float):
    """Processa en enskild TTS-förfrågan."""
    request_started_at = time.time()
    
    try:
        # Kontrollera om denna request redan är cancelled
        if asyncio.current_task().cancelled():
            logger.info("TTS request was cancelled before processing started")
            return
            
        await _send_json(ws, {
            "type": "status", 
            "stage": "processing",
            "text_length": len(text),
            "request_id": int(request_started_at * 1000)  # Unik ID för denna förfrågan
        })

        await _send_json(ws, {"type": "status", "stage": "connecting-elevenlabs"})
        logger.debug("Connecting to ElevenLabs for text: %s", text[:50] + "..." if len(text) > 50 else text)

        # Hantera ElevenLabs API-kommunikation och audio-streaming
        await _send_json(ws, {"type": "status", "stage": "streaming"})
        
        audio_bytes_total = 0
        last_chunk_ts = None
        
        async for server_msg, current_audio_bytes in process_text_to_audio(ws, text, request_started_at):
            # Kontrollera om denna request är cancelled under streaming
            if asyncio.current_task().cancelled():
                logger.info("TTS request was cancelled during streaming")
                return
                
            # Hantera audio-streaming till frontend
            try:
                audio_bytes_total, last_chunk_ts, should_break = await send_audio_to_frontend(
                    ws, server_msg, current_audio_bytes, last_chunk_ts
                )
                
                if should_break:
                    break
            except Exception as e:
                # Om WebSocket är stängd, avbryt snabbt
                if "WebSocket" in str(e) and "closed" in str(e):
                    logger.info("WebSocket closed during streaming, cancelling TTS")
                    return
                raise
        
        # Kontrollera om denna request är cancelled innan vi skickar "done"
        if asyncio.current_task().cancelled():
            logger.info("TTS request was cancelled before completion")
            return
            
        await _send_json(ws, {
            "type": "status",
            "stage": "done",
            "audio_bytes_total": audio_bytes_total,
            "elapsed_sec": round(time.time() - request_started_at, 3),
            "request_id": int(request_started_at * 1000)
        })
        
        logger.info("TTS request completed: %d bytes, %.3fs", audio_bytes_total, time.time() - request_started_at)
        
        # RENSA active_tts_requests när TTS-förfrågan är klar
        if ws in active_tts_requests:
            del active_tts_requests[ws]
            logger.info("✅ Cleared active TTS request after normal completion - channel is now free")
            logger.info("🔍 Remaining active_tts_requests keys: %s", list(active_tts_requests.keys()))
        else:
            logger.warning("⚠️ No active TTS request found for this WebSocket in normal completion")
            logger.info("🔍 Current active_tts_requests keys: %s", list(active_tts_requests.keys()))

    except asyncio.CancelledError:
        logger.info("TTS request was cancelled: %s", text[:50] + "..." if len(text) > 50 else text)
        # Skicka cancellation-meddelande till frontend
        try:
            await _send_json(ws, {
                "type": "status",
                "stage": "cancelled",
                "request_id": int(request_started_at * 1000)
            })
        except Exception:
            pass  # Ignorera fel om WebSocket redan är stängd
        raise  # Re-raise CancelledError så att den hanteras korrekt
        
    except Exception as e:
        logger.error("Error processing TTS request: %s", e)
        await _send_json(ws, {
            "type": "error", 
            "message": str(e),
            "request_id": int(request_started_at * 1000)
        })
    finally:
        # Säkerställ att active_tts_requests rensas även vid fel
        if ws in active_tts_requests:
            del active_tts_requests[ws]
            logger.info("✅ Cleared active TTS request in finally block - channel is now free")
            logger.info("🔍 Remaining active_tts_requests keys: %s", list(active_tts_requests.keys()))
        else:
            logger.info("🔍 No active TTS request found in finally block - channel was already free")
