# app/llm/conversation_manager.py
import logging
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from .config import llm_config

logger = logging.getLogger("llm")

@dataclass
class ConversationMessage:
    """En meddelande i konversationen."""
    role: str  # "user" eller "assistant"
    content: str
    timestamp: datetime

class ConversationManager:
    """Hanterar konversationshistorik per session."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: List[ConversationMessage] = []
        self._add_system_message()
    
    def _add_system_message(self):
        """Lägg till system-prompt som första meddelande."""
        system_msg = ConversationMessage(
            role="system",
            content=llm_config.system_prompt,
            timestamp=datetime.now()
        )
        self.messages.append(system_msg)
    
    def add_user_message(self, content: str):
        """Lägg till användarmeddelande."""
        user_msg = ConversationMessage(
            role="user",
            content=content.strip(),
            timestamp=datetime.now()
        )
        self.messages.append(user_msg)
        logger.debug("Added user message to session %s: %s", self.session_id, content[:50])
    
    def add_assistant_message(self, content: str):
        """Lägg till assistentmeddelande."""
        assistant_msg = ConversationMessage(
            role="assistant",
            content=content.strip(),
            timestamp=datetime.now()
        )
        self.messages.append(assistant_msg)
        logger.debug("Added assistant message to session %s: %s", self.session_id, content[:50])
    
    def get_conversation_context(self) -> List[Dict[str, str]]:
        """Hämta konversationskontext för OpenAI API."""
        # Behåll system-meddelandet + de senaste N utbyten
        max_messages = 1 + (llm_config.max_conversation_history * 2)  # system + (user+assistant pairs)
        
        # Ta de senaste meddelandena
        recent_messages = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        
        # Konvertera till OpenAI-format
        context = []
        for msg in recent_messages:
            context.append({
                "role": msg.role,
                "content": msg.content
            })
        
        logger.debug("Generated context with %d messages for session %s", len(context), self.session_id)
        return context
    
    def clear_history(self):
        """Rensa konversationshistorik (behåll system-meddelandet)."""
        system_msg = self.messages[0]  # Behåll system-meddelandet
        self.messages = [system_msg]
        logger.info("Cleared conversation history for session %s", self.session_id)
    
    def get_message_count(self) -> int:
        """Antal meddelanden (exklusive system)."""
        return len(self.messages) - 1  # Exkludera system-meddelandet
