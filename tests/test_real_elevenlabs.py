import pytest
import asyncio
import time
import json
import base64
import os
from pathlib import Path
from unittest.mock import AsyncMock
from app.tts.text_to_audio import process_text_to_audio
from tests.utils.pcm_to_wav import pcm_to_wav

def test_real_elevenlabs_pipeline():
    """Testar ElevenLabs API med riktig anslutning."""
    
    async def _run_test():
        # Kontrollera att vi har API-nyckel
        ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
        if not ELEVENLABS_API_KEY:
            pytest.skip("Ingen ElevenLabs API-nyckel konfigurerad (sätt ELEVENLABS_API_KEY miljövariabel)")
        
        # Hämta text från miljövariabel eller använd standard
        test_text = os.getenv("TEXT", "Detta är ett test av ElevenLabs API med riktig anslutning!")
        
        print(f"\n🚀 STARTAR RIKTIGT ELEVENLABS TEST")
        print(f"🔑 API-nyckel: {'✅ Konfigurerad' if ELEVENLABS_API_KEY else '❌ Saknas'}")
        print(f"📝 Test-text: '{test_text}'")
        print(f"⏱️  Starttid: {time.strftime('%H:%M:%S')}")
        
        # Simulera websocket
        mock_websocket = AsyncMock()
        
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
                    
        except Exception as e:
            print(f"❌ Fel under ElevenLabs kommunikation: {e}")
            raise
        
        print(f"✅ Mottog {len(audio_chunks)} audio-chunks från ElevenLabs")
        print(f"📊 Total audio bytes: {audio_bytes_total}")
        
        # Skapa audio-fil
        all_audio_data = b""
        for server_msg, _ in audio_chunks:
            if isinstance(server_msg, str):
                try:
                    payload = json.loads(server_msg)
                    if "audio" in payload and payload["audio"]:
                        audio_bytes = base64.b64decode(payload["audio"])
                        all_audio_data += audio_bytes
                except Exception as e:
                    print(f"⚠️  Kunde inte decodera audio: {e}")
            elif isinstance(server_msg, (bytes, bytearray)):
                all_audio_data += server_msg
        
        if all_audio_data:
            # Skapa output-filer
            output_dir = "test_output"
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            pcm_file = f"{output_dir}/REAL_TEST_{timestamp}.pcm"
            wav_file = f"{output_dir}/REAL_TEST_{timestamp}.wav"
            
            # Spara PCM-fil
            with open(pcm_file, "wb") as f:
                f.write(all_audio_data)
            
            print(f"🎵 PCM-fil skapad: {pcm_file}")
            print(f"📁 PCM-storlek: {len(all_audio_data)} bytes")
            
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
        
        # Sammanfattning
        elapsed_time = time.time() - started_at
        print(f"\n🎯 TEST KLART!")
        print(f"⏱️  Total tid: {elapsed_time:.2f} sekunder")
        print(f"📊 Resultat: {len(audio_chunks)} chunks, {len(all_audio_data)} bytes")
        print(f"🔗 PCM-fil: {pcm_file if all_audio_data else 'Ingen'}")
        print(f"🔗 WAV-fil: {wav_path if wav_path else 'Ingen'}")
        
        # Verifiera att testet fungerade
        assert len(audio_chunks) > 0, "Inga audio-chunks mottagna från ElevenLabs"
        assert len(all_audio_data) > 0, "Ingen audio-data genererad"
    
    asyncio.run(_run_test())

def test_real_elevenlabs_short_text():
    """Testar ElevenLabs API med kort text."""
    
    async def _run_test():
        # Kontrollera att vi har API-nyckel
        ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
        if not ELEVENLABS_API_KEY:
            pytest.skip("Ingen ElevenLabs API-nyckel konfigurerad (sätt ELEVENLABS_API_KEY miljövariabel)")
        
        # Hämta text från miljövariabel eller använd standard
        test_text = os.getenv("TEXT", "Hej!")
        
        print(f"\n🚀 STARTAR KORT TEXT TEST")
        print(f"🔑 API-nyckel: {'✅ Konfigurerad' if ELEVENLABS_API_KEY else '❌ Saknas'}")
        print(f"📝 Kort test-text: '{test_text}'")
        print(f"⏱️  Starttid: {time.strftime('%H:%M:%S')}")
        
        # Simulera websocket
        mock_websocket = AsyncMock()
        
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
                    
        except Exception as e:
            print(f"❌ Fel under ElevenLabs kommunikation: {e}")
            raise
        
        print(f"✅ Mottog {len(audio_chunks)} audio-chunks från ElevenLabs")
        print(f"📊 Total audio bytes: {audio_bytes_total}")
        
        # Skapa audio-fil
        all_audio_data = b""
        for server_msg, _ in audio_chunks:
            if isinstance(server_msg, str):
                try:
                    payload = json.loads(server_msg)
                    if "audio" in payload and payload["audio"]:
                        audio_bytes = base64.b64decode(payload["audio"])
                        all_audio_data += audio_bytes
                except Exception as e:
                    print(f"⚠️  Kunde inte decodera audio: {e}")
            elif isinstance(server_msg, (bytes, bytearray)):
                all_audio_data += server_msg
        
        if all_audio_data:
            # Skapa output-filer
            output_dir = "test_output"
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            pcm_file = f"{output_dir}/SHORT_TEST_{timestamp}.pcm"
            wav_file = f"{output_dir}/SHORT_TEST_{timestamp}.wav"
            
            # Spara PCM-fil
            with open(pcm_file, "wb") as f:
                f.write(all_audio_data)
            
            print(f"🎵 PCM-fil skapad: {pcm_file}")
            print(f"📁 PCM-storlek: {len(all_audio_data)} bytes")
            
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
        
        # Sammanfattning
        elapsed_time = time.time() - started_at
        print(f"\n🎯 KORT TEXT TEST KLART!")
        print(f"⏱️  Total tid: {elapsed_time:.2f} sekunder")
        print(f"📊 Resultat: {len(audio_chunks)} chunks, {len(all_audio_data)} bytes")
        print(f"🔗 PCM-fil: {pcm_file if all_audio_data else 'Ingen'}")
        print(f"🔗 WAV-fil: {wav_path if wav_path else 'Ingen'}")
        
        # Verifiera att testet fungerade
        assert len(audio_chunks) > 0, "Inga audio-chunks mottagna från ElevenLabs"
        assert len(all_audio_data) > 0, "Ingen audio-data genererad"
    
    asyncio.run(_run_test())
