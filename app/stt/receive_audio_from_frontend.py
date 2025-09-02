

def process_frontend_message(msg, buffers):
    """
    Hantera meddelande från frontend WebSocket.
    Flyttad från stt_ws.py för att separera concerns.
    """
    if "bytes" in msg and msg["bytes"] is not None:
        chunk = msg["bytes"]
        buffers.frontend_chunks.append(len(chunk))
        return {"type": "audio", "chunk": chunk, "size": len(chunk)}
    elif "text" in msg and msg["text"] is not None:
        if msg["text"] == "ping":
            return {"type": "ping"}
        else:
            return {"type": "text", "text": msg["text"]}
    else:
        return {"type": "unknown"}
