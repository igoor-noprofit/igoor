"""E2E check for localtts sentence streaming: pretends to be the browser UI.

Connects to the app websocket (ws://127.0.0.1:9714/ws/app), triggers the
speak hook over REST, and timestamps play_stream / binary PCM chunks /
play_stream_end arrivals. Confirms the backend protocol and measures the
real time-to-first-chunk through the full plugin path.

A second connection to /ws/asrjs is needed because asrjs's pause_asr
hookimpl waits for its own frontend socket forever when no browser asrjs
client exists (the real app always has one).
"""
import asyncio
import json
import sys
import time

import httpx
import websockets

TEXT = ("Bonjour ! Je suis la voix locale de l'application. "
        "Cette réponse est diffusée phrase par phrase. "
        "Vous devriez entendre la première pendant que le reste est encore généré.")


async def drain(ws):
    while True:
        await ws.recv()


async def main() -> None:
    t_start = time.perf_counter()
    asrjs = await websockets.connect("ws://127.0.0.1:9714/ws/asrjs", max_size=2**24)
    asyncio.get_running_loop().create_task(drain(asrjs))
    async with websockets.connect("ws://127.0.0.1:9714/ws/app", max_size=2**24) as ws:
        async with httpx.AsyncClient(timeout=300) as http:
            status = (await http.get("http://127.0.0.1:9714/api/plugins/localtts/status")).json()
            print("localtts status:", status.get("state"), status.get("detail", ""))
            if status.get("state") != "ready":
                sys.exit("model not ready")

            r = await http.post(
                "http://127.0.0.1:9714/api/hooks/speak",
                json={"message": TEXT, "skip_asr": False},
            )
            print("speak hook:", r.status_code, r.text[:120])

        chunks = 0
        first_chunk = None
        stream_id = None
        play_stream_at = None
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=180)
            t = time.perf_counter() - t_start
            if isinstance(msg, bytes):
                chunks += 1
                if first_chunk is None:
                    first_chunk = t
                    print(f"[{t:7.2f}s] binary chunk #{chunks} ({len(msg)} bytes)")
                else:
                    print(f"[{t:7.2f}s] binary chunk #{chunks} ({len(msg)} bytes)")
            else:
                data = json.loads(msg)
                if "play_stream" in data:
                    # mirror the frontend: a new play_stream replaces the
                    # active stream
                    stream_id = data["play_stream"]["id"]
                    play_stream_at = t
                    chunks = 0
                    first_chunk = None
                    print(f"[{t:7.2f}s] play_stream: {data['play_stream']}")
                elif "play_stream_end" in data:
                    if data["play_stream_end"].get("id") != stream_id:
                        print(f"[{t:7.2f}s] play_stream_end (stale, ignored)")
                        continue
                    print(f"[{t:7.2f}s] play_stream_end: {data['play_stream_end']}")
                    break
                elif data.get("type") != "boot_progress":
                    print(f"[{t:7.2f}s] msg: {str(data)[:90]}")

        # ack playback so the backend's wait_playback_finished completes
        async with httpx.AsyncClient(timeout=300) as http:
            await http.post("http://127.0.0.1:9714/api/hooks/tts_playback_finished", json={})
        print(f"chunks: {chunks}, time-to-first-chunk: {first_chunk:.2f}s "
              f"(+{first_chunk - play_stream_at:.2f}s after play_stream)")
    await asrjs.close()


if __name__ == "__main__":
    asyncio.run(main())
