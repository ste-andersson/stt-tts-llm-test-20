# app/llm/text_to_response.py
import asyncio
import logging
import os
from typing import Optional

import openai
from openai import AsyncOpenAI

from .config import llm_config
from .conversation_manager import ConversationManager

logger = logging.getLogger("llm")

class LLMProcessor:
    """Hanterar LLM-anrop till OpenAI."""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )
    
    async def process_user_input(self, conversation_manager: ConversationManager, user_text: str) -> Optional[str]:
        """
        Processa användarinput genom LLM.
        
        Args:
            conversation_manager: Konversationshanterare för sessionen
            user_text: Användarens transkriberade text
            
        Returns:
            LLM-svar eller None vid fel
        """
        try:
            # Lägg till användarmeddelande
            conversation_manager.add_user_message(user_text)
            
            # Hämta konversationskontext
            messages = conversation_manager.get_conversation_context()
            
            logger.info("Sending request to OpenAI for session %s: %s", 
                       conversation_manager.session_id, user_text[:50])
            
            # Gör OpenAI-anrop
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=llm_config.model,
                    messages=messages,
                    temperature=llm_config.temperature,
                    max_tokens=llm_config.max_tokens
                ),
                timeout=llm_config.request_timeout_seconds
            )
            
            # Extrahera svar
            assistant_response = response.choices[0].message.content.strip()
            
            # Lägg till assistentmeddelande i konversationen
            conversation_manager.add_assistant_message(assistant_response)
            
            logger.info("Received response from OpenAI for session %s: %s", 
                       conversation_manager.session_id, assistant_response[:50])
            
            return assistant_response
            
        except asyncio.TimeoutError:
            logger.error("OpenAI request timeout for session %s", conversation_manager.session_id)
            return None
        except Exception as e:
            logger.error("Error processing LLM request for session %s: %s", 
                        conversation_manager.session_id, str(e))
            return None

# Global instans
llm_processor = LLMProcessor()
