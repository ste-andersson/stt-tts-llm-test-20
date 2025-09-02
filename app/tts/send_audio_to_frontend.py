import base64
import json
import logging
import time

logger = logging.getLogger("stefan-api-test-16")

async def _send_debug_json(ws, obj: dict):
    """Skicka JSON (utf-8) till frontend för debug-meddelanden."""
    try:
        await ws.send_text(json.dumps(obj))
    except Exception as e:
        logger.error("Failed to send debug JSON: %s", e)

async def send_audio_to_frontend(ws, server_msg, audio_bytes_total, last_chunk_ts):
    """Hanterar audio-streaming till frontend."""
    
    # ElevenLabs skickar (vanligen) JSON‐text
    try:
        payload = json.loads(server_msg)
    except Exception:
        # Om binärt (ovanligt), skicka vidare
        if isinstance(server_msg, (bytes, bytearray)):
            await ws.send_bytes(server_msg)
            audio_bytes_total += len(server_msg)
            last_chunk_ts = time.time()
            logger.debug("Forwarded binary frame: %d bytes", len(server_msg))
        else:
            logger.debug("Non-JSON non-bytes frame received (ignored)")
        return audio_bytes_total, last_chunk_ts, False

    # Debug: skicka upp event/meta till frontend (utan base64-datan)
    meta = {k: v for k, v in payload.items() if k not in ("audio", "normalizedAlignment", "alignment")}
    await _send_debug_json(ws, {"type": "debug", "provider": "elevenlabs", "payload": meta})
    logger.debug("ElevenLabs frame keys=%s", list(payload.keys()))

    # Fel från ElevenLabs?
    if payload.get("event") == "error" or "error" in payload:
        err_msg = payload.get("message") or payload.get("error") or "Okänt fel från TTS-leverantören"
        logger.error("ElevenLabs error: %s", err_msg)
        await _send_debug_json(ws, {"type": "error", "message": err_msg})
        return audio_bytes_total, last_chunk_ts, True  # Signal to break

    # Audio‐chunk (base64) – kan vara null/tom → hoppa över
    audio_b64 = payload.get("audio")
    if isinstance(audio_b64, str) and audio_b64:
        try:
            b = base64.b64decode(audio_b64)
            if b:
                await ws.send_bytes(b)
                audio_bytes_total += len(b)
                last_chunk_ts = time.time()
                logger.debug("Forwarded audio chunk: %d bytes (total=%d)", len(b), audio_bytes_total)
        except Exception as e:
            logger.warning("Kunde inte dekoda audio-chunk: %s", e)

    # Slut?
    is_final = payload.get("isFinal") is True or payload.get("event") == "finalOutput"
    if is_final:
        logger.debug("Final frame from ElevenLabs received")
    
    return audio_bytes_total, last_chunk_ts, is_final
