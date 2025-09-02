import os
import base64
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from typing import Dict, Any, List, Optional
import wave
import time

router = APIRouter()

@router.get("/audio-files")
async def list_audio_files() -> Dict[str, Any]:
    """Returnerar lista över audio-filer för dropdown."""
    output_dir = Path("test_output")
    
    if not output_dir.exists():
        return {
            "files": [],
            "message": "Inga audio-filer hittades. Kör ett test först."
        }
    
    # Hitta alla audio-filer
    audio_files = []
    for file_path in output_dir.glob("*"):
        if file_path.is_file() and file_path.suffix.lower() in ['.pcm', '.wav']:
            stat = file_path.stat()
            audio_files.append({
                'name': file_path.name,
                'path': str(file_path),
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'type': file_path.suffix.lower()
            })
    
    # Sortera efter senaste modifiering (nyaste först)
    audio_files.sort(key=lambda x: x['modified'], reverse=True)
    
    return {
        "files": audio_files,
        "message": f"Hittade {len(audio_files)} audio-filer"
    }

@router.get("/download-audio/{filename}")
async def download_audio(filename: str):
    """Laddar ner en audio-fil."""
    file_path = Path("test_output") / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Filen hittades inte")
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type='application/octet-stream'
    )
