async def send_transcription_to_frontend(ws, result: dict, send_json: bool, buffers, session_id: str = None, session_start_time: float = None):
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
            import time
            import logging
            log = logging.getLogger("stt")
            
            # Mät STT-processning
            stt_end_time = time.time()
            stt_duration = 0  # STT-processning är redan klar när vi kommer hit
            
            log.info(f"[LATENS] STT-processning klar: {stt_duration:.3f}s")
            log.info(f"[LATENS] Transkriptionstext: '{result['text'][:50]}{'...' if len(result['text']) > 50 else ''}'")
            
            # Skicka meddelande att LLM-processning pågår
            if send_json:
                await ws.send_json({
                    "type": "stt.processing",
                    "text": result["text"]
                })
            
            # Trigga LLM-pipeline
            await _trigger_llm_pipeline(ws, session_id, result["text"], session_start_time)
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

async def _trigger_llm_pipeline(ws, session_id: str, transcription_text: str, session_start_time: float = None):
    """
    Trigga LLM-pipeline för att processa final transkription.
    
    Args:
        ws: WebSocket-anslutning till frontend
        session_id: Session-ID för konversationen
        transcription_text: Final transkriberad text
    """
    try:
        import time
        import logging
        log = logging.getLogger("stt")
        
        # Mät LLM-processning
        llm_start_time = time.time()
        log.info(f"[LATENS] LLM-processning startar: {llm_start_time:.3f}s")
        
        # Importera LLM-moduler
        from ..llm.receive_text_from_stt import process_final_transcription
        from ..llm.send_response_to_tts import send_llm_response_to_tts
        
        # Processa genom LLM
        llm_response = await process_final_transcription(session_id, transcription_text)
        
        llm_end_time = time.time()
        llm_duration = llm_end_time - llm_start_time
        log.info(f"[LATENS] LLM-processning klar: {llm_duration:.3f}s")
        
        if llm_response:
            # Skicka stt.final med transkriptionen
            await ws.send_json({
                "type": "stt.final",
                "text": transcription_text
            })
            
            # Mät TTS-processning
            tts_start_time = time.time()
            log.info(f"[LATENS] TTS-processning startar: {tts_start_time:.3f}s")
            
            # Skicka LLM-svar till TTS
            await send_llm_response_to_tts(ws, llm_response)
            
            tts_end_time = time.time()
            tts_duration = tts_end_time - tts_start_time
            log.info(f"[LATENS] TTS-processning klar: {tts_duration:.3f}s")
            
            # Beräkna total tid och sammanfattning
            if session_start_time:
                total_time = tts_end_time - session_start_time
                # OpenAI's VAD avgör tystnadsupptäckt, inte backend timeout
                # Vi kan inte mäta exakt när OpenAI's VAD triggar, så vi använder en uppskattning
                estimated_vad_time = 0.5  # Uppskattning baserat på OpenAI's VAD-inställningar
                
                log.info(f"[LATENS] ===== SAMMANFATTNING =====")
                log.info(f"[LATENS] Total tid tills ljudsvar börjar spelas: {total_time:.3f}s")
                log.info(f"[LATENS] - Tystnadsupptäckt: ~{estimated_vad_time:.1f}s (OpenAI's VAD)")
                log.info(f"[LATENS] - STT-processning: {stt_duration:.3f}s")
                log.info(f"[LATENS] - LLM-processning: {llm_duration:.3f}s")
                log.info(f"[LATENS] - TTS-processning: {tts_duration:.3f}s")
                log.info(f"[LATENS] - Annat: {total_time - estimated_vad_time - stt_duration - llm_duration - tts_duration:.3f}s")
                log.info(f"[LATENS] ==========================")
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
