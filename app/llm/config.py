# app/llm/config.py
from pydantic import BaseModel

class LLMConfig(BaseModel):
    """Konfiguration för LLM-modulen."""
    
    # OpenAI-inställningar
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 500
    
    # System-prompt
    system_prompt: str = "Du är en hjälpsam AI-assistent. Du svarar mycket kort och formulerar dig som i ett telefonsamtal."
    
    # Konversationshantering
    max_conversation_history: int = 10  # Antal tidigare utbyten att hålla kvar
    max_response_length: int = 500      # Max längd på LLM-svar
    
    # Timeout-inställningar
    request_timeout_seconds: int = 30   # Timeout för OpenAI-anrop

# Global instans
llm_config = LLMConfig()
