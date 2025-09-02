import pytest
import json
import base64
import asyncio
from unittest.mock import AsyncMock
from app.tts.send_audio_to_frontend import send_audio_to_frontend

def test_audio_chunk_forwarding(mock_websocket):
    """Testar att audio-chunks skickas vidare korrekt."""
    
    async def _run_test():
        # Simulera audio data från ElevenLabs
        audio_data = b'fake_audio_data_123'
        audio_b64 = base64.b64encode(audio_data).decode()
        
        server_msg = json.dumps({
            "audio": audio_b64,
            "event": "audio_chunk"
        })
        
        audio_bytes_total = 0
        last_chunk_ts = None
        
        result_audio_bytes, result_last_chunk_ts, should_break = await send_audio_to_frontend(
            mock_websocket, server_msg, audio_bytes_total, last_chunk_ts
        )
        
        # Verifiera att audio skickades
        mock_websocket.send_bytes.assert_called_once_with(audio_data)
        assert result_audio_bytes == len(audio_data)
        assert result_last_chunk_ts is not None
        assert not should_break
    
    asyncio.run(_run_test())

def test_binary_frame_forwarding(mock_websocket):
    """Testar att binära frames skickas vidare direkt."""
    
    async def _run_test():
        binary_data = b'binary_audio_data'
        audio_bytes_total = 100
        last_chunk_ts = None
        
        result_audio_bytes, result_last_chunk_ts, should_break = await send_audio_to_frontend(
            mock_websocket, binary_data, audio_bytes_total, last_chunk_ts
        )
        
        # Verifiera att binär data skickades direkt
        mock_websocket.send_bytes.assert_called_once_with(binary_data)
        assert result_audio_bytes == audio_bytes_total + len(binary_data)
        assert result_last_chunk_ts is not None
        assert not should_break
    
    asyncio.run(_run_test())

def test_error_handling(mock_websocket):
    """Testar att fel från ElevenLabs hanteras korrekt."""
    
    async def _run_test():
        server_msg = json.dumps({
            "event": "error",
            "message": "API error occurred"
        })
        
        audio_bytes_total = 0
        last_chunk_ts = None
        
        result_audio_bytes, result_last_chunk_ts, should_break = await send_audio_to_frontend(
            mock_websocket, server_msg, audio_bytes_total, last_chunk_ts
        )
        
        # Verifiera att error skickades till frontend
        mock_websocket.send_text.assert_called()
        assert should_break  # Signal att vi ska bryta
    
    asyncio.run(_run_test())

def test_final_frame_detection(mock_websocket):
    """Testar att final frames detekteras korrekt."""
    
    async def _run_test():
        server_msg = json.dumps({
            "audio": base64.b64encode(b'final_chunk').decode(),
            "isFinal": True
        })
        
        audio_bytes_total = 0
        last_chunk_ts = None
        
        result_audio_bytes, result_last_chunk_ts, should_break = await send_audio_to_frontend(
            mock_websocket, server_msg, audio_bytes_total, last_chunk_ts
        )
        
        # Verifiera att final frame hanterades
        assert should_break  # Signal att vi ska bryta
        mock_websocket.send_bytes.assert_called_once()
    
    asyncio.run(_run_test())

def test_empty_audio_handling(mock_websocket):
    """Testar att tomma audio-chunks hanteras korrekt."""
    
    async def _run_test():
        server_msg = json.dumps({
            "audio": "",
            "event": "audio_chunk"
        })
        
        audio_bytes_total = 0
        last_chunk_ts = None
        
        result_audio_bytes, result_last_chunk_ts, should_break = await send_audio_to_frontend(
            mock_websocket, server_msg, audio_bytes_total, last_chunk_ts
        )
        
        # Verifiera att inget audio skickades
        mock_websocket.send_bytes.assert_not_called()
        assert result_audio_bytes == audio_bytes_total
        assert not should_break
    
    asyncio.run(_run_test())

def test_debug_info_sending(mock_websocket):
    """Testar att debug-info skickas till frontend."""
    
    async def _run_test():
        server_msg = json.dumps({
            "audio": base64.b64encode(b'test_audio').decode(),
            "event": "audio_chunk",
            "timestamp": "2024-01-01T12:00:00Z"
        })
        
        audio_bytes_total = 0
        last_chunk_ts = None
        
        await send_audio_to_frontend(
            mock_websocket, server_msg, audio_bytes_total, last_chunk_ts
        )
        
        # Verifiera att debug-info skickades (utan audio-data)
        mock_websocket.send_text.assert_called()
        call_args = mock_websocket.send_text.call_args[0][0]
        debug_data = json.loads(call_args)
        
        assert debug_data["type"] == "debug"
        assert "timestamp" in debug_data["payload"]
        assert "audio" not in debug_data["payload"]  # Audio ska inte vara med i debug
    
    asyncio.run(_run_test())
