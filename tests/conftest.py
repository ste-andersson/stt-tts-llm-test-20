import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

# Konfigurera pytest-asyncio
pytest_plugins = ['pytest_asyncio']

@pytest.fixture
def mock_websocket():
    """Mock WebSocket för tester."""
    ws = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_bytes = AsyncMock()
    ws.close = AsyncMock()
    return ws
