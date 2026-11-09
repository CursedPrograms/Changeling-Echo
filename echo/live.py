"""live.py - an Echo voice, live: other apps pipe their microphone through it.

    <Echo>/venv/Scripts/python.exe echo/live.py echo_female

Runs in Echo's own environment (torch, Applio), so the apps that use it (Changeling CopyCat Realtime, Mosaic Mask)
don't need any of that: they start this as a child process and talk to it through its stdin and stdout.

The conversation, all little-endian:
    on start, Echo writes   b"ECHO" + uint32 chunk                      (when the voice is loaded and warmed up)
    then, over and over:
        the app writes  float32 key + float32[chunk]    (key: the pitch step in semitones; audio: 24 kHz mono)
        Echo writes     float32[chunk]                  (the same stretch, in the Echo voice)
A chunk is a quarter second. The answer is that same quarter second, converted. Applio's own realtime engine
does the work (RMVPE pitch, ContentVec, the voice, cross-fades between chunks), at 48 kHz inside.
"""
import os
import struct
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPLIO = os.path.join(HERE, "Applio")
VOICES = os.path.join(HERE, "voices")
SHARED = r"F:\AIModels\rvc\voices"
RATE = 24000                    # what the apps send and get back
CHUNK = RATE // 4               # a quarter second
UP = 2                          # Applio works at 48 kHz


def voice_files(name):
    """(pth, index or "") for a voice: Echo's voices/, else the shared copy on F:."""
    for folder in (VOICES, SHARED):
        pth = os.path.join(folder, name + ".pth")
        if os.path.exists(pth):
            index = os.path.join(folder, name + ".index")
            return pth, index if os.path.exists(index) else ""
    raise SystemExit(f"no voice called {name} in {VOICES} or {SHARED}")


def _read(stream, n):
    data = b""
    while len(data) < n:
        more = stream.read(n - len(data))
        if not more:
            return None
        data += more
    return data


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "echo_female"
    pth, index = voice_files(name)
    log = sys.stderr
    out = os.fdopen(os.dup(1), "wb")       # the pipe back to the app: only Echo's answers go in it;
    os.dup2(2, 1)                          # everything else anyone prints goes to stderr
    sys.stdout = sys.stderr
    inp = sys.stdin.buffer
    os.chdir(APPLIO)                       # Applio finds its models from its own folder
    sys.path.insert(0, APPLIO)
    from rvc.realtime.core import VoiceChanger
    from scipy.signal import resample_poly

    vc = VoiceChanger(block_frame=CHUNK * UP, cross_fade_overlap_size=0.05, extra_convert_size=0.5,
                      model_path=pth, index_path=index, f0_method="rmvpe", embedder_model="contentvec",
                      silent_threshold=-60)
    params = dict(index_rate=0.5, protect=0.33, volume_envelope=1.0)
    t = np.arange(CHUNK * UP) / (RATE * UP)  # warm up on a buzz (silence skips the model, so it warms nothing):
    buzz = (0.2 * ((t * 140) % 1.0 - 0.5)).astype(np.float32)   # the first real runs are the slow ones
    for _ in range(3):
        vc.on_request(buzz, 0, **params)
    print(f"Echo live: {name} ready ({vc.device})", file=log, flush=True)

    out.write(b"ECHO" + struct.pack("<I", CHUNK))
    out.flush()
    spent, count = 0.0, 0
    while True:
        data = _read(inp, 4 + CHUNK * 4)
        if data is None:
            break
        key = struct.unpack("<f", data[:4])[0]
        audio = np.frombuffer(data[4:], np.float32)
        start = time.perf_counter()
        up = resample_poly(audio, UP, 1).astype(np.float32)       # 24 -> 48 kHz
        result, _vol, _perf = vc.on_request(up, float(key), **params)
        down = resample_poly(np.asarray(result, np.float32), 1, UP)  # 48 -> 24 kHz
        out.write(np.clip(down, -1, 1).astype("<f4").tobytes())
        out.flush()
        spent += time.perf_counter() - start
        count += 1
        if count % 40 == 0:
            print(f"Echo live: {spent / count * 1000:.0f} ms per {CHUNK * 1000 // RATE} ms chunk", file=log, flush=True)
            spent, count = 0.0, 0


if __name__ == "__main__":
    main()
