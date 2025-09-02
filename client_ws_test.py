# client_ws_test.py
import asyncio, json, wave, argparse, websockets

def read_chunks(w, chunk_ms):
    bytes_per_sec = w.getframerate() * w.getnchannels() * w.getsampwidth()
    chunk_bytes = int(bytes_per_sec * (chunk_ms/1000.0))
    frames_per_chunk = chunk_bytes // (w.getnchannels() * w.getsampwidth())
    while True:
        data = w.readframes(frames_per_chunk)
        if not data:
            break
        yield data

async def run(url, wav, chunk_ms):
    async with websockets.connect(url) as ws:
        # få session_id
        msg = await ws.recv()
        try:
            j = json.loads(msg)
            print("SERVER:", j)
            session_id = j.get("session_id")
        except Exception:
            print("SERVER:", msg)
            session_id = None

        # läs och skicka PCM16-chunks i “real-time”
        with wave.open(wav, 'rb') as w:
            assert w.getframerate()==16000 and w.getnchannels()==1 and w.getsampwidth()==2, \
                "WAV måste vara 16kHz, mono, 16-bit"
            async def recv_task():
                try:
                    async for incoming in ws:
                        # backend skickar text-deltas (och ev. JSON först)
                        try:
                            j = json.loads(incoming)
                            print("SERVER:", j)
                        except Exception:
                            print("Δ", incoming, flush=True)
                except Exception:
                    pass

            rtask = asyncio.create_task(recv_task())
            for chunk in read_chunks(w, chunk_ms):
                await ws.send(chunk)
                await asyncio.sleep(chunk_ms/1000.0)

            # liten paus för sista commit
            await asyncio.sleep(1.0)
            rtask.cancel()

        if session_id:
            print("\nAnvänd session_id för debug-endpoints:")
            print(f"  curl 'http://localhost:8000/debug/openai-text?session_id={session_id}'")
            print(f"  curl 'http://localhost:8000/debug/frontend-chunks?session_id={session_id}'")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="ws://localhost:8000/ws/transcribe")
    p.add_argument("--wav", required=True)
    p.add_argument("--chunk-ms", type=int, default=100)
    a = p.parse_args()
    asyncio.run(run(a.url, a.wav, a.chunk_ms))
