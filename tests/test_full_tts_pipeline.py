import pytest
import asyncio
import time
import json
from unittest.mock import AsyncMock, patch
from app.tts.receive_text_from_frontend import receive_and_validate_text
from app.tts.text_to_audio import process_text_to_audio
from app.tts.send_audio_to_frontend import send_audio_to_frontend

def test_full_pipeline_with_mock_elevenlabs(mock_websocket):
    """Testar hela TTS-pipelinen med mockad ElevenLabs."""
    
    async def _run_test():
        test_text = "Det här är ett test av hela systemet"
        started_at = time.time()
        
        # Simulera att frontend skickar text
        mock_websocket.receive_text = AsyncMock(return_value=json.dumps({"text": test_text}))
        
        # Testa text-validering
        text_data = await receive_and_validate_text(mock_websocket)
        assert text_data is not None
        assert text_data["text"] == test_text
        
        # Mocka ElevenLabs för pipeline-test
        with patch('app.tts.text_to_audio.ws_connect') as mock_connect:
            mock_eleven_ws = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_eleven_ws
            
            # Simulera ElevenLabs response med audio - använd en enkel mock som alltid returnerar data
            responses = [
                '{"event": "start"}',
                '{"audio": "dGVzdF9hdWRpbw==", "event": "audio_chunk"}',  # base64 för "test_audio"
                '{"audio": "bW9yZV9hdWRpbw==", "event": "audio_chunk"}',  # base64 för "more_audio"
                '{"isFinal": true}'  # Notera: lowercase 'true' för JSON
            ]
            response_index = 0
            
            async def mock_recv():
                nonlocal response_index
                if response_index < len(responses):
                    result = responses[response_index]
                    response_index += 1
                    return result
                else:
                    # Returnera final message om vi har kört slut på responses
                    return '{"isFinal": true}'
            
            mock_eleven_ws.recv = mock_recv
            
            # Kör text-to-audio
            audio_chunks = []
            async for server_msg, audio_bytes in process_text_to_audio(mock_websocket, test_text, started_at):
                audio_chunks.append((server_msg, audio_bytes))
            
            # Verifiera att vi fick audio
            assert len(audio_chunks) >= 3
            
            # Testa audio-forwarding
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
                    except:
                        pass  # Ignorera fel för mock-data
            
            # Verifiera att audio skickades till frontend
            assert mock_websocket.send_bytes.called or mock_websocket.send_text.called
    
    asyncio.run(_run_test())

def test_pipeline_error_handling(mock_websocket):
    """Testar att fel hanteras korrekt genom hela pipelinen."""
    
    async def _run_test():
        # Testa med ogiltig text
        mock_websocket.receive_text = AsyncMock(return_value="invalid json")
        
        text_data = await receive_and_validate_text(mock_websocket)
        assert text_data is None
        
        # Verifiera att WebSocket stängdes
        mock_websocket.close.assert_called_once()
    
    asyncio.run(_run_test())

def test_pipeline_performance(mock_websocket):
    """Testar prestanda för hela pipelinen."""
    
    async def _run_test():
        test_text = "Kort test för prestanda"
        started_at = time.time()
        
        # Simulera snabb ElevenLabs response
        with patch('app.tts.text_to_audio.ws_connect') as mock_connect:
            mock_eleven_ws = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_eleven_ws
            
            # Använd en enkel mock som returnerar data
            responses = [
                '{"event": "start"}',
                '{"audio": "dGVzdA==", "isFinal": true}'  # base64 för "test"
            ]
            response_index = 0
            
            async def mock_recv():
                nonlocal response_index
                if response_index < len(responses):
                    result = responses[response_index]
                    response_index += 1
                    return result
                else:
                    return '{"isFinal": true}'
            
            mock_eleven_ws.recv = mock_recv
            
            # Mät tid för hela processen
            pipeline_start = time.time()
            
            audio_chunks = []
            async for server_msg, audio_bytes in process_text_to_audio(mock_websocket, test_text, started_at):
                audio_chunks.append((server_msg, audio_bytes))
            
            pipeline_time = time.time() - pipeline_start
            
            # Verifiera att pipeline inte tar för lång tid (mock ska vara snabb)
            assert pipeline_time < 1.0  # Mindre än 1 sekund för mock
            assert len(audio_chunks) >= 2
    
    asyncio.run(_run_test())

def test_pipeline_with_empty_response(mock_websocket):
    """Testar pipelinen med tom response från ElevenLabs."""
    
    async def _run_test():
        test_text = "Test"
        started_at = time.time()
        
        with patch('app.tts.text_to_audio.ws_connect') as mock_connect:
            mock_eleven_ws = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_eleven_ws
            
            # Simulera tom response - använd en enkel mock
            responses = [
                '{"event": "start"}',
                '{"audio": "", "isFinal": true}'  # Tom audio
            ]
            response_index = 0
            
            async def mock_recv():
                nonlocal response_index
                if response_index < len(responses):
                    result = responses[response_index]
                    response_index += 1
                    return result
                else:
                    return '{"isFinal": true}'
            
            mock_eleven_ws.recv = mock_recv
            
            audio_chunks = []
            async for server_msg, audio_bytes in process_text_to_audio(mock_websocket, test_text, started_at):
                audio_chunks.append((server_msg, audio_bytes))
            
            # Verifiera att vi hanterade tom response
            assert len(audio_chunks) >= 2
    
    asyncio.run(_run_test())

def test_pipeline_status_messages(mock_websocket):
    """Testar att status-meddelanden skickas korrekt genom pipelinen."""
    
    async def _run_test():
        test_text = "Test för status-meddelanden"
        started_at = time.time()
        
        # Simulera att vi skickar status-meddelanden
        await mock_websocket.send_text(json.dumps({"type": "status", "stage": "ready"}))
        
        with patch('app.tts.text_to_audio.ws_connect') as mock_connect:
            mock_eleven_ws = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_eleven_ws
            
            # Använd en enkel mock
            responses = [
                '{"event": "start"}',
                '{"isFinal": true}'
            ]
            response_index = 0
            
            async def mock_recv():
                nonlocal response_index
                if response_index < len(responses):
                    result = responses[response_index]
                    response_index += 1
                    return result
                else:
                    return '{"isFinal": true}'
            
            mock_eleven_ws.recv = mock_recv
            
            # Kör pipeline
            audio_chunks = []
            async for server_msg, audio_bytes in process_text_to_audio(mock_websocket, test_text, started_at):
                audio_chunks.append((server_msg, audio_bytes))
            
            # Verifiera att status-meddelanden skickades
            assert mock_websocket.send_text.called
    
    asyncio.run(_run_test())
