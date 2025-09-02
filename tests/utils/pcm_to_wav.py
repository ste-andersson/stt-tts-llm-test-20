#!/usr/bin/env python3
"""
Verktyg för att konvertera PCM-filer till WAV-format.
ElevenLabs skickar PCM 16kHz 16-bit, vilket vi konverterar till WAV.
"""

import wave
import os
import sys
from pathlib import Path

def pcm_to_wav(pcm_file_path, wav_file_path=None, sample_rate=16000, channels=1, sample_width=2):
    """
    Konverterar PCM-fil till WAV-format.
    
    Args:
        pcm_file_path: Sökväg till PCM-filen
        wav_file_path: Sökväg för WAV-filen (om None, skapas automatiskt)
        sample_rate: Sampling rate (default: 16000 Hz för ElevenLabs)
        channels: Antal kanaler (default: 1 för mono)
        sample_width: Bredd per sample i bytes (default: 2 för 16-bit)
    """
    
    if not os.path.exists(pcm_file_path):
        raise FileNotFoundError(f"PCM-fil hittades inte: {pcm_file_path}")
    
    # Skapa WAV-filnamn om inte angivet
    if wav_file_path is None:
        pcm_path = Path(pcm_file_path)
        wav_file_path = pcm_path.with_suffix('.wav')
    
    print(f"🔄 Konverterar {pcm_file_path} → {wav_file_path}")
    
    # Läs PCM-data
    with open(pcm_file_path, 'rb') as pcm_file:
        pcm_data = pcm_file.read()
    
    print(f"📊 PCM-data: {len(pcm_data)} bytes")
    
    # Skapa WAV-fil
    with wave.open(wav_file_path, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    
    # Verifiera WAV-filen
    with wave.open(wav_file_path, 'rb') as wav_file:
        frames = wav_file.getnframes()
        duration = frames / sample_rate
    
    print(f"✅ WAV skapad: {wav_file_path}")
    print(f"📊 WAV-info: {frames} frames, {duration:.2f}s, {sample_rate}Hz")
    
    return wav_file_path

def main():
    """Huvudfunktion för kommandoradsanvändning."""
    if len(sys.argv) < 2:
        print("Användning: python pcm_to_wav.py <pcm-fil> [wav-fil]")
        print("Exempel: python pcm_to_wav.py test_output/audio.pcm")
        sys.exit(1)
    
    pcm_file = sys.argv[1]
    wav_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        wav_path = pcm_to_wav(pcm_file, wav_file)
        print(f"🎵 Konvertering klar: {wav_path}")
    except Exception as e:
        print(f"❌ Fel vid konvertering: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
