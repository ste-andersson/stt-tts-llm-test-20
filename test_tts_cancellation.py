#!/usr/bin/env python3
"""
Test script för att verifiera TTS cancellation fungerar korrekt.
Detta test simulerar flera snabba TTS-förfrågningar för att se att nya avbryter gamla.
"""

import asyncio
import json
import logging
import time
import websockets
from typing import List

# Konfigurera logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TTSClient:
    def __init__(self, uri: str = "ws://localhost:8000/ws/tts"):
        self.uri = uri
        self.websocket = None
        self.responses: List[dict] = []
        
    async def connect(self):
        """Anslut till TTS WebSocket."""
        try:
            self.websocket = await websockets.connect(self.uri)
            logger.info("Ansluten till TTS WebSocket")
            return True
        except Exception as e:
            logger.error(f"Kunde inte ansluta: {e}")
            return False
    
    async def send_tts_request(self, text: str, request_id: str = None):
        """Skicka TTS-förfrågan."""
        if not self.websocket:
            logger.error("Inte ansluten")
            return False
            
        message = {
            "type": "tts_request",
            "text": text
        }
        
        if request_id:
            message["request_id"] = request_id
            
        try:
            await self.websocket.send(json.dumps(message))
            logger.info(f"Skickat TTS-förfrågan: '{text[:30]}...'")
            return True
        except Exception as e:
            logger.error(f"Fel vid sändning: {e}")
            return False
    
    async def listen_for_responses(self, duration: float = 10.0):
        """Lyssna på svar från servern."""
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration:
                try:
                    response = await asyncio.wait_for(
                        self.websocket.recv(), 
                        timeout=1.0
                    )
                    
                    data = json.loads(response)
                    self.responses.append(data)
                    
                    # Logga viktiga statusuppdateringar
                    if data.get("type") == "status":
                        stage = data.get("stage")
                        request_id = data.get("request_id", "unknown")
                        
                        if stage == "processing":
                            logger.info(f"🔄 Bearbetar (ID: {request_id})")
                        elif stage == "streaming":
                            logger.info(f"🎵 Streamar (ID: {request_id})")
                        elif stage == "done":
                            logger.info(f"✅ Klar (ID: {request_id})")
                        elif stage == "cancelled":
                            logger.info(f"❌ Avbruten (ID: {request_id})")
                            
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Fel vid mottagning: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Fel i listen_for_responses: {e}")
    
    async def close(self):
        """Stäng anslutningen."""
        if self.websocket:
            await self.websocket.close()
            logger.info("Anslutning stängd")

async def test_cancellation():
    """Testa att nya TTS-förfrågningar avbryter gamla."""
    logger.info("🚀 Startar TTS cancellation test...")
    
    client = TTSClient()
    
    if not await client.connect():
        logger.error("Kunde inte ansluta till servern")
        return
    
    # Starta listener i bakgrunden
    listener_task = asyncio.create_task(client.listen_for_responses(15.0))
    
    try:
        # Skicka första förfrågan (lång text som tar tid)
        logger.info("📤 Skickar första TTS-förfrågan (lång text)...")
        await client.send_tts_request(
            "Detta är en mycket lång text som kommer att ta ganska lång tid att konvertera till tal. "
            "Den innehåller många ord och meningar för att simulera en verklig situation där användaren "
            "skickar en längre text som sedan behöver avbrytas när en ny, kortare text kommer in.",
            "request_1"
        )
        
        # Vänta lite så att första förfrågan hinner börja
        await asyncio.sleep(1.0)
        
        # Skicka andra förfrågan (kort text som ska avbryta första)
        logger.info("📤 Skickar andra TTS-förfrågan (kort text som ska avbryta första)...")
        await client.send_tts_request(
            "Kort svar.",
            "request_2"
        )
        
        # Vänta lite till
        await asyncio.sleep(1.0)
        
        # Skicka tredje förfrågan (ännu kortare)
        logger.info("📤 Skickar tredje TTS-förfrågan (mycket kort text)...")
        await client.send_tts_request(
            "OK.",
            "request_3"
        )
        
        # Vänta tills listener är klar
        await listener_task
        
    except Exception as e:
        logger.error(f"Fel under test: {e}")
    finally:
        await client.close()
    
    # Analysera resultat
    logger.info("\n📊 Testresultat:")
    logger.info(f"Totalt antal svar: {len(client.responses)}")
    
    # Räkna olika typer av svar
    status_responses = [r for r in client.responses if r.get("type") == "status"]
    cancelled_responses = [r for r in status_responses if r.get("stage") == "cancelled"]
    done_responses = [r for r in status_responses if r.get("stage") == "done"]
    
    logger.info(f"Status-svar: {len(status_responses)}")
    logger.info(f"Avbrutna förfrågningar: {len(cancelled_responses)}")
    logger.info(f"Slutförda förfrågningar: {len(done_responses)}")
    
    # Kontrollera att vi fick cancellation-meddelanden
    if cancelled_responses:
        logger.info("✅ SUCCESS: Fick cancellation-meddelanden!")
        for resp in cancelled_responses:
            logger.info(f"   - Avbruten request ID: {resp.get('request_id')}")
    else:
        logger.warning("⚠️  WARNING: Inga cancellation-meddelanden mottagna")
    
    # Kontrollera att sista förfrågan slutfördes
    if done_responses:
        last_done = done_responses[-1]
        logger.info(f"✅ Sista slutförda förfrågan ID: {last_done.get('request_id')}")
    else:
        logger.warning("⚠️  WARNING: Inga slutförda förfrågningar")

if __name__ == "__main__":
    asyncio.run(test_cancellation())
