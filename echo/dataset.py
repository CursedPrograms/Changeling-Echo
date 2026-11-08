"""dataset.py - the speech a voice is trained on.

A built-in voice (Piper: Amy for female, Ryan for male) reads corpus.txt aloud in three deliveries (steady,
quicker and livelier, slower and calmer), about 17 minutes in all, as WAV files in dataset/<voice>/. Your own
voice works too: put recordings (WAV, at least 10 minutes, one speaker, no music) in a folder and train from
that instead.

Piper is the one DREAM speaks with: this file runs itself under DREAM's Python (PIPER_PYTHON, default
DREAM's venv311), where the piper package is, and loads the voice once. Nothing is downloaded; the voices are
in piper_voices/.

    python echo/dataset.py female      (what make() runs)
"""
import os
import subprocess
import sys
import wave

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPER_PYTHON = os.environ.get("PIPER_PYTHON", r"D:\cc\DREAM Robotics Ecosystem\DREAM\venv311\Scripts\python.exe")
VOICES = {"female": "en_US-amy-medium", "male": "en_US-ryan-medium"}
# (speed: Piper's length scale, above 1 is slower; how much the delivery varies)
DELIVERIES = [(1.0, 0.667), (0.9, 0.8), (1.15, 0.5)]


def corpus():
    with open(os.path.join(HERE, "echo", "corpus.txt"), encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def seconds(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def folder(voice):
    return os.path.join(HERE, "dataset", voice)


def minutes(path):
    """Minutes of speech in a folder of WAVs."""
    total = 0.0
    for f in os.listdir(path):
        if f.lower().endswith(".wav"):
            total += seconds(os.path.join(path, f))
    return total / 60


def make(voice, progress=None):
    """Speak the corpus with a built-in voice; returns (folder, minutes of speech)."""
    if voice not in VOICES:
        raise ValueError(f"no built-in voice called {voice}")
    if not os.path.exists(PIPER_PYTHON):
        raise FileNotFoundError(f"no Python with piper at {PIPER_PYTHON} (set PIPER_PYTHON)")
    proc = subprocess.Popen([PIPER_PYTHON, os.path.abspath(__file__), voice], stdout=subprocess.PIPE, text=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for line in proc.stdout:
        if line.startswith("step ") and progress:
            done, total = map(int, line.split()[1].split("/"))
            progress(done, total)
    if proc.wait() != 0:
        raise RuntimeError("Piper failed (see the console)")
    return folder(voice), minutes(folder(voice))


def _speak(voice):
    """Runs under PIPER_PYTHON: load the voice once, speak every line in every delivery."""
    from piper import PiperVoice, SynthesisConfig

    model = os.path.join(HERE, "piper_voices", VOICES[voice] + ".onnx")
    speaker = PiperVoice.load(model)
    out = folder(voice)
    os.makedirs(out, exist_ok=True)
    lines = corpus()
    jobs = [(i, line, d) for d in range(len(DELIVERIES)) for i, line in enumerate(lines)]
    for n, (i, line, d) in enumerate(jobs):
        path = os.path.join(out, f"{voice}_{d}_{i:03d}.wav")
        if not os.path.exists(path):
            scale, noise = DELIVERIES[d]
            with wave.open(path, "wb") as w:
                speaker.synthesize_wav(line, w, syn_config=SynthesisConfig(length_scale=scale, noise_scale=noise))
        print(f"step {n + 1}/{len(jobs)}", flush=True)


if __name__ == "__main__":
    _speak(sys.argv[1])
