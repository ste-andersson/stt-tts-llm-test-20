import pytest
import asyncio
import time
import json
import base64
import os
from pathlib import Path
from unittest.mock import AsyncMock
from app.tts.receive_text_from_frontend import receive_and_validate_text
from app.tts.text_to_audio import process_text_to_audio
from app.tts.send_audio_to_frontend import send_audio_to_frontend
from tests.utils.pcm_to_wav import pcm_to_wav

def test_full_chain_with_real_elevenlabs():
    """Testar HELA kedjan från frontend till audio-fil som skickas till frontend."""
    
    async def _run_test():
        # Kontrollera att vi har API-nyckel
        ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
        if not ELEVENLABS_API_KEY:
            pytest.skip("Ingen ElevenLabs API-nyckel konfigurerad (sätt ELEVENLABS_API_KEY miljövariabel)")
        
        print(f"\n🚀 STARTAR HELA KEDJAN - från frontend till audio-fil")
        print(f"🔑 API-nyckel: {'✅ Konfigurerad' if ELEVENLABS_API_KEY else '❌ Saknas'}")
        
        # 1. Simulera frontend som skickar text
        mock_websocket = AsyncMock()
        test_text = os.getenv("TEXT", "Detta är ett test av hela TTS-kedjan från frontend till audio-fil!")
        mock_websocket.receive_text = AsyncMock(return_value=json.dumps({"text": test_text}))
        
        print(f"📝 Frontend skickar text: '{test_text}'")
        print(f"⏱️  Starttid: {time.strftime('%H:%M:%S')}")
        
        # 2. Testa text-validering (första steget i kedjan)
        print("\n✅ STEG 1: Text-validering från frontend")
        text_data = await receive_and_validate_text(mock_websocket)
        assert text_data is not None
        assert text_data["text"] == test_text
        print(f"✅ Text validerad: '{text_data['text']}'")
        
        # 3. Skicka text till ElevenLabs (andra steget i kedjan)
        print("\n🎵 STEG 2: Ansluter till ElevenLabs API")
        started_at = time.time()
        
        audio_chunks = []
        audio_bytes_total = 0
        
        try:
            async for server_msg, audio_bytes in process_text_to_audio(mock_websocket, test_text, started_at):
                audio_chunks.append((server_msg, audio_bytes))
                audio_bytes_total += audio_bytes if audio_bytes else 0
                
                # Visa progress
                if isinstance(server_msg, str):
                    try:
                        payload = json.loads(server_msg)
                        if "event" in payload:
                            print(f"📡 ElevenLabs: {payload['event']}")
                        if "audio" in payload:
                            print(f"🎵 Audio chunk mottaget ({len(payload['audio'])} chars)")
                    except:
                        pass
                elif isinstance(server_msg, (bytes, bytearray)):
                    print(f"🔊 Binary audio: {len(server_msg)} bytes")
                
                # Bryt om vi har fått tillräckligt med data
                if len(audio_chunks) > 10:  # Förhindra oändlig loop
                    break
                    
        except Exception as e:
            print(f"❌ Fel under ElevenLabs kommunikation: {e}")
            raise
        
        print(f"✅ Mottog {len(audio_chunks)} audio-chunks från ElevenLabs")
        print(f"📊 Total audio bytes: {audio_bytes_total}")
        
        # 4. Testa audio-forwarding (tredje steget i kedjan)
        print("\n🔄 STEG 3: Audio-forwarding till frontend")
        audio_bytes_total = 0
        last_chunk_ts = None
        
        for server_msg, _ in audio_chunks:
            if isinstance(server_msg, str):
                try:
                    audio_bytes_total, last_chunk_ts, should_break = await send_audio_to_frontend(
                        mock_websocket, server_msg, audio_bytes_total, last_chunk_ts
                    )
                    if should_break:
                        break
                except Exception as e:
                    print(f"⚠️  Varning vid audio-forwarding: {e}")
        
        # 5. Skapa audio-fil som skickas till frontend
        print("\n💾 STEG 4: Skapar audio-fil som skickas till frontend")
        
        # Samla all audio-data som faktiskt skickas till frontend
        all_audio_data = b""
        for server_msg, _ in audio_chunks:
            if isinstance(server_msg, str):
                try:
                    payload = json.loads(server_msg)
                    if "audio" in payload and payload["audio"]:
                        # Decodera base64 audio (som görs i send_audio_to_frontend)
                        audio_bytes = base64.b64decode(payload["audio"])
                        all_audio_data += audio_bytes
                        print(f"🎵 Decoderade {len(audio_bytes)} bytes från base64")
                except Exception as e:
                    print(f"⚠️  Kunde inte decodera audio: {e}")
            elif isinstance(server_msg, (bytes, bytearray)):
                all_audio_data += server_msg
                print(f"🔊 Binary audio: {len(server_msg)} bytes")
        
        if all_audio_data:
            # Skapa output-filer
            output_dir = "test_output"
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            pcm_file = f"{output_dir}/FRONTEND_AUDIO_{timestamp}.pcm"
            wav_file = f"{output_dir}/FRONTEND_AUDIO_{timestamp}.wav"
            
            # Spara PCM-fil
            with open(pcm_file, "wb") as f:
                f.write(all_audio_data)
            
            print(f"🎵 PCM-fil skapad: {pcm_file}")
            print(f"📁 PCM-storlek: {len(all_audio_data)} bytes")
            print(f"💡 Detta är rå PCM-data som skickas till frontend!")
            
            # Konvertera till WAV
            try:
                wav_path = pcm_to_wav(pcm_file, wav_file)
                print(f"🎵 WAV-fil skapad: {wav_path}")
            except Exception as e:
                print(f"⚠️  Kunde inte konvertera till WAV: {e}")
                wav_path = None
            
            print(f"🌐 Öppna i webbläsaren för att spela upp:")
            print(f"   http://localhost:8000/api/audio-files")
            print(f"   Eller på Render: https://din-app.onrender.com/api/audio-files")
            
            # Verifiera att vi faktiskt fick audio
            assert len(all_audio_data) > 0, "Ingen audio-data mottagen från ElevenLabs"
            assert len(audio_chunks) > 0, "Inga audio-chunks mottagna"
            
        else:
            print("⚠️  Ingen audio-data att spara")
            pcm_file = None
            wav_path = None
        
        # 6. Verifiera att audio skickades till frontend
        print("\n✅ STEG 5: Verifierar att audio skickades till frontend")
        assert mock_websocket.send_bytes.called or mock_websocket.send_text.called
        print("✅ Audio skickades till frontend")
        
        # 7. Sammanfattning
        elapsed_time = time.time() - started_at
        print(f"\n🎯 HELA KEDJAN KLAR!")
        print(f"⏱️  Total tid: {elapsed_time:.2f} sekunder")
        print(f"📊 Resultat: {len(audio_chunks)} chunks, {len(all_audio_data)} bytes")
        print(f"🔗 PCM-fil: {pcm_file if all_audio_data else 'Ingen'}")
        print(f"🔗 WAV-fil: {wav_path if wav_path else 'Ingen'}")
        
        # Verifiera att hela kedjan fungerade
        assert text_data is not None, "Text-validering misslyckades"
        assert len(audio_chunks) > 0, "Inga audio-chunks mottagna från ElevenLabs"
        assert len(all_audio_data) > 0, "Ingen audio-data genererad"
        assert mock_websocket.send_bytes.called or mock_websocket.send_text.called, "Audio skickades inte till frontend"
        
        print(f"\n✅ ALLA STEG I KEDJAN FUNGERADE!")
        print(f"🎵 Du kan nu spela upp ljudet i webbläsaren!")
    
    asyncio.run(_run_test())
