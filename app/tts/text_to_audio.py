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


def calculate_simple_timeout(text_length: int) -> int:
    """
    Enkel timeout som bara används som fallback om ElevenLabs inte skickar "isFinal".
    
    Strategi:
    1. Lita på ElevenLabs "isFinal" signaler för naturlig avslutning
    2. Använd bara timeout som fallback för att undvika att hänga
    3. Mycket generös timeout eftersom vi litar på ElevenLabs
    """
    # Generös timeout som bara används som fallback
    if text_length <= 100:
        return 8  # 8 sekunder för korta meddelanden
    elif text_length <= 300:
        return 15  # 15 sekunder för medellånga meddelanden
    else:
        return 25  # 25 sekunder för långa meddelanden

async def process_text_to_audio(ws, text, started_at):
    """Hanterar ElevenLabs API-kommunikation och returnerar rå data."""
    
    # 2) Anslut till ElevenLabs
    query = f"?model_id={DEFAULT_MODEL_ID}&output_format=pcm_16000"
    eleven_ws_url = f"wss://api.elevenlabs.io/v1/text-to-speech/{DEFAULT_VOICE_ID}/stream-input{query}"
    headers = [("xi-api-key", ELEVENLABS_API_KEY)]
    
    # Logga API-detaljer i terminalen
    logger.info("Connecting to ElevenLabs with voice_id=%s, model_id=%s", DEFAULT_VOICE_ID, DEFAULT_MODEL_ID)
    
    # Beräkna enkel timeout som fallback
    text_length = len(text)
    audio_bytes_total = 0
    
    # Enkel timeout som bara används som fallback
    fallback_timeout_sec = calculate_simple_timeout(text_length)
    logger.info("Text: %d chars, fallback timeout: %ds (litar på ElevenLabs 'isFinal')", 
                text_length, fallback_timeout_sec)

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
                # Använd enkel timeout som fallback - lita på ElevenLabs "isFinal"
                server_msg = await asyncio.wait_for(eleven.recv(), timeout=fallback_timeout_sec)
            except asyncio.TimeoutError:
                # Fallback timeout - ElevenLabs skickade inte "isFinal" inom rimlig tid
                logger.warning("ElevenLabs fallback timeout after %ds (audio_bytes=%d), aborting stream", 
                             fallback_timeout_sec, audio_bytes_total)
                break
            except asyncio.CancelledError:
                logger.info("TTS request was cancelled during ElevenLabs receive")
                break

            # Returnera rå data från ElevenLabs
            yield server_msg, audio_bytes_total

            # Uppdatera audio_bytes_total för binary frames
            if isinstance(server_msg, (bytes, bytearray)):
                audio_bytes_total += len(server_msg)

            # Lita på att send_audio_to_frontend hanterar isFinal-signaler
            # Vi behöver inte hantera det här eftersom tts_ws.py gör det

        logger.info("Stream done: audio_bytes_total=%d elapsed=%.3fs", audio_bytes_total, time.time() - started_at)
