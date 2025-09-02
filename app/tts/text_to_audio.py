import asyncio
import logging
import time
import os
from websockets.client import connect as ws_connect
import orjson

logger = logging.getLogger("stefan-api-test-16")

# TTS-specifika inställningar
DEFAULT_VOICE_ID = "Vo4adEN1y46b0ufuysRe"  # Sätt ditt voice-ID här
DEFAULT_MODEL_ID = "eleven_flash_v2_5"
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")  # Hämtas från .env


def calculate_dynamic_timeout(text_length: int) -> int:
    """
    Beräknar dynamisk timeout baserat på textlängd.
    
    Formel: 
    - Bas-timeout: 3 sekunder
    - Extra tid: 0.1 sekund per 10 tecken
    - Min: 3s, Max: 30s
    """
    base_timeout = 3
    extra_time = (text_length / 10) * 0.1  # 0.1s per 10 tecken
    total_timeout = base_timeout + extra_time
    
    # Begränsa mellan 3 och 30 sekunder
    return max(3, min(30, int(total_timeout)))

async def process_text_to_audio(ws, text, started_at):
    """Hanterar ElevenLabs API-kommunikation och returnerar rå data."""
    
    # 2) Anslut till ElevenLabs
    query = f"?model_id={DEFAULT_MODEL_ID}&output_format=pcm_16000"
    eleven_ws_url = f"wss://api.elevenlabs.io/v1/text-to-speech/{DEFAULT_VOICE_ID}/stream-input{query}"
    headers = [("xi-api-key", ELEVENLABS_API_KEY)]
    
    # Logga API-detaljer i terminalen
    logger.info("Connecting to ElevenLabs with voice_id=%s, model_id=%s", DEFAULT_VOICE_ID, DEFAULT_MODEL_ID)
    
    # Beräkna dynamisk timeout baserat på textlängd
    text_length = len(text)
    inactivity_timeout_sec = calculate_dynamic_timeout(text_length)
    logger.info("Text length: %d chars, calculated timeout: %ds", text_length, inactivity_timeout_sec)

    audio_bytes_total = 0

    async with ws_connect(eleven_ws_url, extra_headers=headers, open_timeout=5) as eleven:
        # 3) Initiera session
        init_msg = {
            "text": " ",  # kickstart
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.8,
                "use_speaker_boost": False,
                "speed": 1.0,
            },
            "generation_config": {
                # Lägre trösklar → snabbare start på kort text
                "chunk_length_schedule": [50, 90, 140]
            },
            "xi_api_key": ELEVENLABS_API_KEY,
        }
        await eleven.send(orjson.dumps(init_msg).decode())
        logger.debug("Sent init message to ElevenLabs")
        
        # Ta bort onödig debug-information som kan orsaka uppehåll

        # 4) Skicka text och trigga generering direkt
        await eleven.send(orjson.dumps({"text": text, "try_trigger_generation": True}).decode())
        logger.debug("Sent user text (%d chars) with try_trigger_generation=True", len(text))

        # 5) Avsluta inmatning (förhindra deras 20s-timeout)
        await eleven.send(orjson.dumps({"text": "", "flush": True}).decode())
        logger.debug("Sent flush message to ElevenLabs")

        # 6) Läs streamen och returnera rå data
        while True:
            # Kontrollera om denna request är cancelled
            if asyncio.current_task().cancelled():
                logger.info("TTS request was cancelled during ElevenLabs streaming")
                break
                
            try:
                server_msg = await asyncio.wait_for(eleven.recv(), timeout=inactivity_timeout_sec)
            except asyncio.TimeoutError:
                # Vi har inte fått något på N sekunder → ge upp snyggt
                logger.warning("No data from ElevenLabs for %ss, aborting stream", inactivity_timeout_sec)
                break
            except asyncio.CancelledError:
                logger.info("TTS request was cancelled during ElevenLabs receive")
                break

            # Returnera rå data från ElevenLabs
            yield server_msg, audio_bytes_total

            # Uppdatera audio_bytes_total för binary frames
            if isinstance(server_msg, (bytes, bytearray)):
                audio_bytes_total += len(server_msg)

            # Slut?
            if isinstance(server_msg, str):
                try:
                    payload = orjson.loads(server_msg)
                    if payload.get("isFinal") is True or payload.get("event") == "finalOutput":
                        logger.debug("Final frame from ElevenLabs received")
                        break
                except:
                    pass

        logger.info("Stream done: audio_bytes_total=%d elapsed=%.3fs", audio_bytes_total, time.time() - started_at)
