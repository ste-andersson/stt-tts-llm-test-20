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


def calculate_aggressive_timeout(text_length: int, audio_bytes_received: int = 0) -> int:
    """
    Aggressiv timeout-strategi med flera steg för att eliminera blockering.
    
    Strategi:
    1. Börja med korta timeouts (2-3 sekunder)
    2. Öka gradvis om audio fortfarande kommer in
    3. Men ha strikta max-gränser för att undvika oändlig väntan
    4. Använd audio-aktivitet för att justera timeout dynamiskt
    """
    # Bas-timeout baserat på text-längd (mycket kortare än tidigare)
    if text_length <= 50:
        base_timeout = 4  # 2 sekunder för mycket korta meddelanden
    elif text_length <= 100:
        base_timeout = 8  # 3 sekunder för korta meddelanden
    elif text_length <= 200:
        base_timeout = 14  # 4 sekunder för medellånga meddelanden
    elif text_length <= 400:
        base_timeout = 22  # 5 sekunder för långa meddelanden
    else:
        base_timeout = 26  # 6 sekunder för mycket långa meddelanden
    
    # Justera baserat på audio-aktivitet
    if audio_bytes_received > 0:
        # Om vi redan har fått audio, använd kortare timeout
        adjusted_timeout = max(1, base_timeout - 1)
    else:
        # Om vi inte har fått någon audio än, använd bas-timeout
        adjusted_timeout = base_timeout
    
    # Max-gräns för att undvika oändlig väntan
    max_timeout = 8
    
    final_timeout = min(adjusted_timeout, max_timeout)
    
    logger.debug("Timeout calculation: text_len=%d, audio_bytes=%d, base=%d, adjusted=%d, final=%d", 
                text_length, audio_bytes_received, base_timeout, adjusted_timeout, final_timeout)
    
    return final_timeout

async def process_text_to_audio(ws, text, started_at):
    """Hanterar ElevenLabs API-kommunikation och returnerar rå data."""
    
    # 2) Anslut till ElevenLabs
    query = f"?model_id={DEFAULT_MODEL_ID}&output_format=pcm_16000"
    eleven_ws_url = f"wss://api.elevenlabs.io/v1/text-to-speech/{DEFAULT_VOICE_ID}/stream-input{query}"
    headers = [("xi-api-key", ELEVENLABS_API_KEY)]
    
    # Logga API-detaljer i terminalen
    logger.info("Connecting to ElevenLabs with voice_id=%s, model_id=%s", DEFAULT_VOICE_ID, DEFAULT_MODEL_ID)
    
    # Beräkna aggressiv timeout-strategi
    text_length = len(text)
    audio_bytes_total = 0
    last_audio_time = time.time()
    consecutive_empty_receives = 0
    
    # Initial timeout (mycket kortare)
    current_timeout_sec = calculate_aggressive_timeout(text_length, 0)
    logger.info("🚀 AGGRESSIVE TIMEOUT: Text: %d chars, initial timeout: %ds (max 8s)", 
                text_length, current_timeout_sec)

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

        # 6) Läs streamen med aggressiv timeout-strategi
        while True:
            # Kontrollera om denna request är cancelled
            if asyncio.current_task().cancelled():
                logger.info("TTS request was cancelled during ElevenLabs streaming")
                break
            
            # Uppdatera timeout baserat på audio-aktivitet
            current_timeout_sec = calculate_aggressive_timeout(text_length, audio_bytes_total)
            
            # Kontrollera om det har gått för lång tid sedan senaste audio
            time_since_last_audio = time.time() - last_audio_time
            if time_since_last_audio > 3.0 and audio_bytes_total > 0:
                logger.warning("🛑 No audio for %.1fs, aborting stream (audio_bytes=%d)", 
                             time_since_last_audio, audio_bytes_total)
                break
                
            try:
                # Använd dynamisk timeout - mycket kortare än tidigare
                server_msg = await asyncio.wait_for(eleven.recv(), timeout=current_timeout_sec)
                consecutive_empty_receives = 0  # Reset counter
            except asyncio.TimeoutError:
                consecutive_empty_receives += 1
                logger.warning("⏰ ElevenLabs timeout after %ds (audio_bytes=%d, empty_receives=%d)", 
                             current_timeout_sec, audio_bytes_total, consecutive_empty_receives)
                
                # Om vi har fått audio men inget nytt på 2+ timeouts, avsluta
                if consecutive_empty_receives >= 2 and audio_bytes_total > 0:
                    logger.warning("🛑 Multiple timeouts with audio received, aborting stream")
                    break
                # Om vi inte har fått någon audio på 3+ timeouts, avsluta
                elif consecutive_empty_receives >= 3:
                    logger.warning("🛑 Multiple timeouts with no audio, aborting stream")
                    break
                else:
                    continue  # Försök igen med samma timeout
                    
            except asyncio.CancelledError:
                logger.info("TTS request was cancelled during ElevenLabs receive")
                break

            # Returnera rå data från ElevenLabs
            yield server_msg, audio_bytes_total

            # Uppdatera audio_bytes_total och timing för binary frames
            if isinstance(server_msg, (bytes, bytearray)):
                audio_bytes_total += len(server_msg)
                last_audio_time = time.time()
                logger.debug("🎵 Received audio chunk: %d bytes (total=%d)", len(server_msg), audio_bytes_total)

            # Lita på att send_audio_to_frontend hanterar isFinal-signaler
            # Vi behöver inte hantera det här eftersom tts_ws.py gör det

        logger.info("Stream done: audio_bytes_total=%d elapsed=%.3fs", audio_bytes_total, time.time() - started_at)
