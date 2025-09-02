# app/llm/send_response_to_tts.py
import asyncio
import logging
from typing import Optional

logger = logging.getLogger("llm")

async def send_llm_response_to_tts(ws, llm_response: str) -> bool:
    """
    Skicka signal till frontend att LLM-svar är redo för TTS.
    
    Args:
        ws: WebSocket-anslutning till frontend (STT WebSocket)
        llm_response: Text från LLM som ska konverteras till audio
        
    Returns:
        True om signalen skickades, False annars
    """
    if not llm_response or not llm_response.strip():
        logger.warning("Empty LLM response, skipping TTS")
        return False
    
    try:
        logger.info("Sending LLM response to frontend for TTS: %s", llm_response[:50])
        
        # Skicka signal till frontend att LLM-svar är redo
        await ws.send_json({
            "type": "llm_response_ready",
            "text": llm_response,
            "instruction": "send_to_tts"
        })
        
        logger.info("Successfully sent LLM response signal to frontend")
        return True
        
    except Exception as e:
        logger.error("Error sending LLM response signal: %s", str(e))
        
        # Skicka felmeddelande till frontend
        try:
            await ws.send_json({
                "type": "error",
                "message": f"Failed to send LLM response: {str(e)}"
            })
        except Exception:
            pass
        
        return False
