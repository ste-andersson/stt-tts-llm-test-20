# Text validation module
import json
from typing import Optional

# Text-validering inställningar
MAX_TEXT_CHARS = 1000  # Max antal tecken för text-input

async def _send_error_json(ws, message: str):
    """Skicka felmeddelande till frontend."""
    try:
        await ws.send_text(json.dumps({"type": "error", "message": message}))
    except Exception:
        pass  # Ignorera fel vid sändning av felmeddelande

async def receive_and_validate_text(ws):
    # 1) Ta emot klientens första meddelande
    raw = await ws.receive_text()
    try:
        data = json.loads(raw)
    except Exception:
        await _send_error_json(ws, "Invalid JSON")
        await ws.close(code=1003)
        return

    text: Optional[str] = (data.get("text") or "").strip()

    if not text:
        await _send_error_json(ws, "Tom text")
        await ws.close(code=1003)
        return

    if len(text) > MAX_TEXT_CHARS:
        await _send_error_json(ws, f"Max {MAX_TEXT_CHARS} tecken")
        await ws.close(code=1009)
        return

    return {"text": text}
