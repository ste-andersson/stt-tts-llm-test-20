# app/llm/receive_text_from_stt.py
import logging
from typing import Optional

from .conversation_manager import ConversationManager
from .text_to_response import llm_processor

logger = logging.getLogger("llm")

# Global session manager - håller koll på alla aktiva konversationer
_conversation_sessions: dict[str, ConversationManager] = {}

def get_or_create_conversation(session_id: str) -> ConversationManager:
    """Hämta eller skapa konversationshanterare för session."""
    if session_id not in _conversation_sessions:
        _conversation_sessions[session_id] = ConversationManager(session_id)
        logger.info("Created new conversation manager for session %s", session_id)
    
    return _conversation_sessions[session_id]

async def process_final_transcription(session_id: str, transcription_text: str) -> Optional[str]:
    """
    Processa final transkription genom LLM-pipeline.
    
    Args:
        session_id: Session-ID för konversationen
        transcription_text: Final transkriberad text från STT
        
    Returns:
        LLM-svar eller None vid fel
    """
    if not transcription_text or not transcription_text.strip():
        logger.warning("Empty transcription text for session %s", session_id)
        return None
    
    try:
        # Hämta konversationshanterare
        conversation_manager = get_or_create_conversation(session_id)
        
        # Processa genom LLM
        llm_response = await llm_processor.process_user_input(
            conversation_manager, 
            transcription_text
        )
        
        if llm_response:
            logger.info("Successfully processed transcription for session %s: %s -> %s", 
                       session_id, transcription_text[:30], llm_response[:30])
            return llm_response
        else:
            logger.error("Failed to get LLM response for session %s", session_id)
            return None
            
    except Exception as e:
        logger.error("Error processing final transcription for session %s: %s", 
                    session_id, str(e))
        return None

def clear_conversation(session_id: str):
    """Rensa konversation för session."""
    if session_id in _conversation_sessions:
        _conversation_sessions[session_id].clear_history()
        logger.info("Cleared conversation for session %s", session_id)

def get_conversation_stats(session_id: str) -> dict:
    """Hämta statistik för konversation."""
    if session_id not in _conversation_sessions:
        return {"message_count": 0, "session_exists": False}
    
    manager = _conversation_sessions[session_id]
    return {
        "message_count": manager.get_message_count(),
        "session_exists": True
    }
