import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch
from app.tts.text_to_audio import process_text_to_audio

def test_text_to_audio_connection(mock_websocket):
    """Testar att anslutning till ElevenLabs fungerar."""
    
    async def _run_test():
        test_text = "Det här är ett test"
        started_at = time.time()
        
        # Mocka websockets.client.connect för att undvika riktiga API-anrop
        with patch('app.tts.text_to_audio.ws_connect') as mock_connect:
            mock_eleven_ws = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_eleven_ws
            
            # Simulera ElevenLabs response
            mock_eleven_ws.recv = AsyncMock(side_effect=[
                '{"event": "start"}',
                b'audio_chunk_1',  # Simulerar audio data
                b'audio_chunk_2',
                '{"isFinal": true}'
            ])
            
            # Kör testet
            audio_chunks = []
            async for server_msg, audio_bytes in process_text_to_audio(mock_websocket, test_text, started_at):
                audio_chunks.append((server_msg, audio_bytes))
            
            # Verifiera att ElevenLabs anropades
            mock_connect.assert_called_once()
            mock_eleven_ws.send.assert_called()
            
            # Verifiera att vi fick audio chunks
            assert len(audio_chunks) >= 3
            assert any(isinstance(chunk[0], bytes) for chunk in audio_chunks)
    
    asyncio.run(_run_test())

def test_text_to_audio_with_long_text(mock_websocket):
    """Testar att längre text hanteras korrekt."""
    
    async def _run_test():
        long_text = "Det här är en längre text som testar att systemet kan hantera fler ord och längre meningar utan problem."
        started_at = time.time()
        
        with patch('app.tts.text_to_audio.ws_connect') as mock_connect:
            mock_eleven_ws = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_eleven_ws
            
            mock_eleven_ws.recv = AsyncMock(side_effect=[
                '{"event": "start"}',
                b'audio_chunk_1',
                '{"isFinal": true}'
            ])
            
            audio_chunks = []
            async for server_msg, audio_bytes in process_text_to_audio(mock_websocket, long_text, started_at):
                audio_chunks.append((server_msg, audio_bytes))
            
            # Verifiera att text skickades till ElevenLabs
            assert mock_eleven_ws.send.called
    
    asyncio.run(_run_test())

def test_text_to_audio_timeout_handling(mock_websocket):
    """Testar att timeout hanteras korrekt."""
    
    async def _run_test():
        test_text = "Test"
        started_at = time.time()
        
        with patch('app.tts.text_to_audio.ws_connect') as mock_connect:
            mock_eleven_ws = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_eleven_ws
            
            # Simulera timeout (ingen data kommer)
            mock_eleven_ws.recv = AsyncMock(side_effect=asyncio.TimeoutError())
            
            audio_chunks = []
            async for server_msg, audio_bytes in process_text_to_audio(mock_websocket, test_text, started_at):
                audio_chunks.append((server_msg, audio_bytes))
            
            # Verifiera att vi hanterade timeout snyggt
            assert len(audio_chunks) == 0
    
    asyncio.run(_run_test())

def test_text_to_audio_error_handling(mock_websocket):
    """Testar att fel från ElevenLabs hanteras."""
    
    async def _run_test():
        test_text = "Test"
        started_at = time.time()
        
        with patch('app.tts.text_to_audio.ws_connect') as mock_connect:
            mock_eleven_ws = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_eleven_ws
            
            # Simulera fel från ElevenLabs - använd en generator som inte tar slut
            async def mock_recv():
                yield '{"event": "error", "message": "API error"}'
                # Lägg till en final message så loopen avslutas
                yield '{"isFinal": true}'
            
            mock_eleven_ws.recv = mock_recv().__anext__
            
            audio_chunks = []
            async for server_msg, audio_bytes in process_text_to_audio(mock_websocket, test_text, started_at):
                audio_chunks.append((server_msg, audio_bytes))
            
            # Verifiera att vi fick error-meddelandet
            assert len(audio_chunks) >= 1
            assert any("error" in str(chunk[0]) for chunk in audio_chunks)
    
    asyncio.run(_run_test())
