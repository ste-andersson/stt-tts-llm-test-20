import asyncio
import json
import logging
import time
import orjson
from fastapi import WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

from ..tts.receive_text_from_frontend import receive_and_validate_text
from ..tts.text_to_audio import process_text_to_audio
from ..tts.send_audio_to_frontend import send_audio_to_frontend

logger = logging.getLogger("stefan-api-test-16")

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
                            
                            # Processa TTS-förfrågan
                            await _process_tts_request(ws, text, session_started_at)
                        
                        # Hantera disconnect-förfrågan
                        elif data.get("type") == "disconnect":
                            logger.info("Client requested disconnect")
                            break
                        
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
        try:
            await ws.close()
        except Exception:
            pass
        logger.info("TTS WebSocket connection closed")


async def _process_tts_request(ws: WebSocket, text: str, session_started_at: float):
    """Processa en enskild TTS-förfrågan."""
    request_started_at = time.time()
    
    try:
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
            # Hantera audio-streaming till frontend
            audio_bytes_total, last_chunk_ts, should_break = await send_audio_to_frontend(
                ws, server_msg, current_audio_bytes, last_chunk_ts
            )
            
            if should_break:
                break
        
        await _send_json(ws, {
            "type": "status",
            "stage": "done",
            "audio_bytes_total": audio_bytes_total,
            "elapsed_sec": round(time.time() - request_started_at, 3),
            "request_id": int(request_started_at * 1000)
        })
        
        logger.info("TTS request completed: %d bytes, %.3fs", audio_bytes_total, time.time() - request_started_at)

    except Exception as e:
        logger.error("Error processing TTS request: %s", e)
        await _send_json(ws, {
            "type": "error", 
            "message": str(e),
            "request_id": int(request_started_at * 1000)
        })
