import pytest
import json
from unittest.mock import AsyncMock
from app.tts.receive_text_from_frontend import receive_and_validate_text

@pytest.mark.asyncio
async def test_valid_text_received(mock_websocket):
    """Testar att giltig text tas emot korrekt."""
    # Simulera att frontend skickar text
    mock_websocket.receive_text = AsyncMock(return_value=json.dumps({"text": "Det här är ett test"}))
    
    result = await receive_and_validate_text(mock_websocket)
    
    assert result is not None
    assert result["text"] == "Det här är ett test"
    mock_websocket.send_text.assert_not_called()  # Ingen error skickas
    mock_websocket.close.assert_not_called()

@pytest.mark.asyncio
async def test_empty_text_rejected(mock_websocket):
    """Testar att tom text avvisas."""
    mock_websocket.receive_text = AsyncMock(return_value=json.dumps({"text": ""}))
    
    result = await receive_and_validate_text(mock_websocket)
    
    assert result is None
    mock_websocket.send_text.assert_called_once()
    mock_websocket.close.assert_called_once_with(code=1003)

@pytest.mark.asyncio
async def test_whitespace_only_text_rejected(mock_websocket):
    """Testar att text med bara mellanslag avvisas."""
    mock_websocket.receive_text = AsyncMock(return_value=json.dumps({"text": "   "}))
    
    result = await receive_and_validate_text(mock_websocket)
    
    assert result is None
    mock_websocket.send_text.assert_called_once()
    mock_websocket.close.assert_called_once_with(code=1003)

@pytest.mark.asyncio
async def test_text_too_long_rejected(mock_websocket):
    """Testar att för lång text avvisas."""
    long_text = "a" * 1001  # Över 1000 tecken
    mock_websocket.receive_text = AsyncMock(return_value=json.dumps({"text": long_text}))
    
    result = await receive_and_validate_text(mock_websocket)
    
    assert result is None
    mock_websocket.send_text.assert_called_once()
    mock_websocket.close.assert_called_once_with(code=1009)

@pytest.mark.asyncio
async def test_invalid_json_rejected(mock_websocket):
    """Testar att ogiltig JSON avvisas."""
    mock_websocket.receive_text = AsyncMock(return_value="invalid json")
    
    result = await receive_and_validate_text(mock_websocket)
    
    assert result is None
    mock_websocket.send_text.assert_called_once()
    mock_websocket.close.assert_called_once_with(code=1003)

@pytest.mark.asyncio
async def test_missing_text_field_rejected(mock_websocket):
    """Testar att JSON utan text-fält avvisas."""
    mock_websocket.receive_text = AsyncMock(return_value=json.dumps({"other": "field"}))
    
    result = await receive_and_validate_text(mock_websocket)
    
    assert result is None
    mock_websocket.send_text.assert_called_once()
    mock_websocket.close.assert_called_once_with(code=1003)
