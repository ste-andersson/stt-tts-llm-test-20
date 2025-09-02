async def send_transcription_to_frontend(ws, result: dict, send_json: bool, buffers, session_id: str = None):
    """
    Skicka transkriptionstext till frontend och trigga LLM-pipeline för final transkription.
    Flyttad från stt_ws.py för att separera concerns.
    
    Args:
        ws: WebSocket-anslutning till frontend
        result: Resultat från process_realtime_event
        send_json: Om JSON-format ska användas
        buffers: Debug store buffers för logging
        session_id: Session-ID för LLM-konversation
    """
    if result["type"] == "transcript" and result["delta"]:
        # Logga för debug
        buffers.openai_text.append(result["text"])
        
        # Logga delta för debug
        buffers.frontend_text.append(result["delta"])
        
        # Om detta är en final transkription, trigga LLM-pipeline istället för att skicka stt.final
        if result["is_final"] and session_id and result["text"].strip():
            # Skicka meddelande att LLM-processning pågår
            if send_json:
                await ws.send_json({
                    "type": "stt.processing",
                    "text": result["text"]
                })
            
            # Trigga LLM-pipeline
            await _trigger_llm_pipeline(ws, session_id, result["text"])
        else:
            # För partial transkriptioner, skicka som vanligt
            if send_json:
                await ws.send_json({
                    "type": "stt.partial",
                    "text": result["text"]
                })
            else:
                await ws.send_text(result["delta"])  # fallback: ren text
        
        return result["text"]  # Returnera text för att uppdatera last_text
    return None

async def _trigger_llm_pipeline(ws, session_id: str, transcription_text: str):
    """
    Trigga LLM-pipeline för att processa final transkription.
    
    Args:
        ws: WebSocket-anslutning till frontend
        session_id: Session-ID för konversationen
        transcription_text: Final transkriberad text
    """
    try:
        # Importera LLM-moduler
        from ..llm.receive_text_from_stt import process_final_transcription
        from ..llm.send_response_to_tts import send_llm_response_to_tts
        
        # Processa genom LLM
        llm_response = await process_final_transcription(session_id, transcription_text)
        
        if llm_response:
            # Skicka stt.final med transkriptionen
            await ws.send_json({
                "type": "stt.final",
                "text": transcription_text
            })
            
            # Skicka LLM-svar till TTS
            await send_llm_response_to_tts(ws, llm_response)
        else:
            # Om LLM misslyckades, skicka stt.final ändå och felmeddelande
            await ws.send_json({
                "type": "stt.final",
                "text": transcription_text
            })
            await ws.send_json({
                "type": "error",
                "message": "Failed to get response from AI"
            })
            
    except Exception as e:
        import logging
        logger = logging.getLogger("stt")
        logger.error("Error in LLM pipeline for session %s: %s", session_id, str(e))
        
        # Skicka felmeddelande till frontend
        try:
            await ws.send_json({
                "type": "error",
                "message": f"AI processing failed: {str(e)}"
            })
        except Exception:
            pass
