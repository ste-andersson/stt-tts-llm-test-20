def process_realtime_event(evt: dict, last_text: str, buffers) -> dict:
    """
    Hantera Realtime event och konvertera till text.
    Flyttad från stt_ws.py för att separera concerns.
    
    Args:
        evt: Realtime event från OpenAI
        last_text: Senaste kända text för delta-beräkning
        buffers: Debug store buffers för logging
        
    Returns:
        Dict med event-resultat eller None om inget text hittades
    """
    t = evt.get("type")

    # (A) logga alltid eventtyp för felsökning
    try:
        buffers.rt_events.append(str(t))
    except Exception:
        pass

    # (B) hantera error/info events
    if t == "error":
        return {
            "type": "error",
            "detail": evt.get("error", evt)
        }
    
    if t == "session.updated":
        return {
            "type": "info",
            "msg": "realtime_connected_and_configured"
        }

    # (C) försök extrahera transcript från flera varianter
    transcript = None

    # 1) Klassisk Realtime-transkript (som repo 2 använder) - whisper-1 + server VAD
    if t == "conversation.item.input_audio_transcription.completed":
        transcript = (
            evt.get("transcript")
            or evt.get("item", {}).get("content", [{}])[0].get("transcript")
        )

    # 2) Alternativ nomenklatur: response.audio_transcript.delta/completed
    if not transcript and t in ("response.audio_transcript.delta", "response.audio_transcript.completed"):
        transcript = evt.get("transcript") or evt.get("text") or evt.get("delta")

    # 3) Sista fallback: response.output_text.delta (text-delning)
    if not transcript and t == "response.output_text.delta":
        delta_txt = evt.get("delta")
        if isinstance(delta_txt, str):
            transcript = (last_text or "") + delta_txt

    if not isinstance(transcript, str) or not transcript:
        return None

    # (D) beräkna delta och returnera text-resultat
    delta = transcript[len(last_text):] if transcript.startswith(last_text) else transcript
    
    # Bestäm om detta är final eller partial transcript
    is_final = t in (
        "conversation.item.input_audio_transcription.completed",
        "response.audio_transcript.completed",
    )
    
    return {
        "type": "transcript",
        "text": transcript,
        "delta": delta,
        "is_final": is_final,
        "event_type": t
    }
