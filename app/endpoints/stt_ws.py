import asyncio
import logging
import os
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from starlette.websockets import WebSocketState

from ..config import settings
from ..debug_store import store
from ..stt.audio_to_event import AudioToEventClient
from ..stt.receive_audio_from_frontend import process_frontend_message
from ..stt.event_to_text import process_realtime_event
from ..stt.send_transcription_to_frontend import send_transcription_to_frontend

log = logging.getLogger("stt")

router = APIRouter()

@router.websocket("/ws/transcribe")
async def ws_transcribe(ws: WebSocket):
    await ws.accept()
    
    # A är default: JSON, B som fallback: ren text
    mode = (ws.query_params.get("mode") or os.getenv("WS_DEFAULT_MODE", "json")).lower()
    send_json = (mode == "json")
    
    session_id = store.new_session()
    
    # Skicka "ready" meddelande för kompatibilitet med frontend
    if send_json:
        await ws.send_json({
            "type": "ready",
            "audio_in": {"encoding": "pcm16", "sample_rate_hz": 16000, "channels": 1},
            "audio_out": {"mimetype": "audio/mpeg"},
        })
        await ws.send_json({"type": "session.started", "session_id": session_id})

    # Setup klient mot OpenAI/Azure Realtime
    rt = AudioToEventClient()  # Använder nu sina egna defaults/miljövariabler
    
    try:
        await rt.connect()
    except Exception as e:
        if send_json and ws.client_state == WebSocketState.CONNECTED:
            await ws.send_json({"type": "error", "reason": "realtime_connect_failed", "detail": str(e)})
        return
    else:
        if send_json and ws.client_state == WebSocketState.CONNECTED:
            await ws.send_json({"type": "info", "msg": "realtime_connected"})

    buffers = store.get_or_create(session_id)

    # Hålla senaste text för enkel diff
    last_text = ""
    
    # Flagga för att veta om vi har skickat ljud
    has_audio = False
    last_audio_time = 0  # Timestamp för senaste ljud
    
    # Latens-mätningar
    session_start_time = time.time()
    first_audio_time = None
    last_commit_time = 0
    
    # Pipeline timing
    silence_detection_start = None
    stt_start_time = None
    llm_start_time = None
    tts_start_time = None
    audio_playback_start = None

    # Task: läs events från Realtime och skicka deltas till frontend
    async def on_rt_event(evt: dict):
        nonlocal last_text
        
        # Använd den nya modulen för att hantera events
        result = process_realtime_event(evt, last_text, buffers)
        
        if not result:
            return
            
        # Hantera error/info events
        if result["type"] == "error":
            if send_json and ws.client_state == WebSocketState.CONNECTED:
                await ws.send_json({"type": "error", "reason": "realtime_error", "detail": result["detail"]})
            return
            
        if result["type"] == "info":
            if send_json and ws.client_state == WebSocketState.CONNECTED:
                await ws.send_json({"type": "info", "msg": result["msg"]})
            return
            
        # Hantera transcript events
        if result["type"] == "transcript" and ws.client_state == WebSocketState.CONNECTED:
            last_text = await send_transcription_to_frontend(ws, result, send_json, buffers, session_id, session_start_time) or last_text

    rt_recv_task = asyncio.create_task(rt.recv_loop(on_rt_event))

    # Periodisk commit för att få löpande partials
    async def commit_loop():
        try:
            while True:
                commit_interval = int(os.getenv("COMMIT_INTERVAL_MS", "150"))
                await asyncio.sleep(max(0.001, commit_interval / 1000))
                # Bara committa om vi har skickat ljud
                if has_audio:
                    # Kontrollera om det har gått för lång tid sedan senaste ljudet
                    import time
                    if time.time() - last_audio_time > 0.7:  # 0.7 sekunder timeout
                        has_audio = False
                        current_time = time.time()
                        timeout_duration = current_time - last_audio_time
                        
                        # Mät tystnadsupptäckt
                        silence_detection_start = current_time
                        silence_detection_duration = timeout_duration
                        
                        log.info(f"[LATENS] Tystnadsupptäckt: {silence_detection_duration:.3f}s sedan senaste ljuddata")
                        log.debug("Timeout - återställer has_audio flaggan")
                        
                        # Skicka timeout-meddelande till frontend
                        if send_json and ws.client_state == WebSocketState.CONNECTED:
                            await ws.send_json({
                                "type": "stt.timeout",
                                "message": "No audio received for 0.7 seconds - waiting for final transcription"
                            })
                        continue
                    
                    try:
                        await rt.commit()
                    except Exception as e:
                        # Hantera "buffer too small" fel mer elegant
                        if "buffer too small" in str(e) or "input_audio_buffer_commit_empty" in str(e):
                            log.debug("Buffer för liten, väntar på mer ljud: %s", e)
                            # Om buffern är helt tom, återställ has_audio flaggan
                            if "0.00ms of audio" in str(e):
                                has_audio = False
                            continue  # Fortsätt loopen istället för att bryta
                        else:
                            log.warning("Commit fel: %s", e)
                            break
        except asyncio.CancelledError:
            pass

    commit_task = asyncio.create_task(commit_loop())

    try:
        while ws.client_state == WebSocketState.CONNECTED:
            try:
                msg = await ws.receive()

                # Använd den nya modulen för att hantera meddelanden
                result = process_frontend_message(msg, buffers)

                # Hantera ljudmeddelande
                if result["type"] == "audio":
                    try:
                        await rt.send_audio_chunk(result["chunk"])
                        buffers.openai_chunks.append(result["size"])
                        has_audio = True  # Markera att vi har skickat ljud
                        import time
                        last_audio_time = time.time()  # Uppdatera timestamp
                    except Exception as e:
                        log.error("Fel när chunk skickades till Realtime: %s", e)
                        break

                # Hantera ping-meddelande
                elif result["type"] == "ping":
                    await ws.send_text("pong")

            except WebSocketDisconnect:
                log.info("WebSocket stängd: %s", session_id)
                break
            except RuntimeError as e:
                log.info("WS disconnect during receive(): %s", e)
                break
            except Exception as e:
                log.error("WebSocket fel: %s", e)
                break
    finally:
        commit_task.cancel()
        rt_recv_task.cancel()
        try:
            await rt.close()
        except Exception:
            pass
        try:
            await asyncio.gather(commit_task, rt_recv_task, return_exceptions=True)
        except Exception:
            pass
        # Stäng WebSocket bara om den inte redan är stängd
        if ws.client_state != WebSocketState.DISCONNECTED:
            try:
                await ws.close()
            except Exception:
                pass


# Alias route för /ws som använder samma logik som /ws/transcribe
@router.websocket("/ws")
async def ws_alias(ws: WebSocket):
    # Återanvänd exakt samma logik som i ws_transcribe
    await ws_transcribe(ws)
