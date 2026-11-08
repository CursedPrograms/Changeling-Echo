"""train.py - turn a folder of speech into an RVC voice: voices/<name>.pth and voices/<name>.index.

Four stages, each Applio's own command line (core.py, in Applio/, run in Echo's venv):
    1. preprocess  slice the speech into short pieces at 40 kHz
    2. extract     each piece's pitch (RMVPE) and its sound (ContentVec)
    3. train       teach a voice model (HiFi-GAN, starting from Applio's pretrained one), N epochs
    4. index       the search index that makes the voice sound more like the speaker
Then the newest weights and the index are copied to voices/, where CopyCat Realtime and Mosaic Mask take them.
"""
import glob
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPLIO = os.path.join(HERE, "Applio")
VOICES = os.path.join(HERE, "voices")
PYTHON = sys.executable
SAMPLE_RATE = 40000
STAGES = ["Slicing the speech", "Reading pitch and sound", "Training", "Indexing"]


def _run(args, stage, progress, epochs=None):
    """One Applio command; reports (stage, fraction or None) as it goes."""
    proc = subprocess.Popen([PYTHON, "core.py", *map(str, args)], cwd=APPLIO, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    tail = []
    for line in proc.stdout:
        line = line.rstrip()
        if not line:
            continue
        tail = (tail + [line])[-12:]
        if epochs:
            m = re.search(r"epoch[=: ]+(\d+)", line, re.I)
            if m and progress:
                progress(stage, min(1.0, int(m.group(1)) / epochs))
        print(line, flush=True)
    if proc.wait() != 0 or any("failed" in t.lower() for t in tail[-2:]):
        raise RuntimeError(f"{STAGES[stage]} failed: " + (tail[-1] if tail else "no output"))


def train(name, dataset, epochs=300, batch_size=8, progress=None):
    """Train voices/<name>.pth (+ .index) from the WAVs in `dataset`. progress(stage, fraction or None)."""
    cores = max(1, (os.cpu_count() or 4) - 1)
    say = progress or (lambda *a: None)

    say(0, None)
    _run(["preprocess", "--model-name", name, "--dataset-path", dataset, "--sample-rate", SAMPLE_RATE,
          "--cpu-cores", cores, "--cut-preprocess", "Automatic", "--chunk-len", 3.0, "--overlap-len", 0.3,
          "--normalization-mode", "post"], 0, progress)
    say(1, None)
    _run(["extract", "--model-name", name, "--f0-method", "rmvpe", "--cpu-cores", cores, "--gpu", 0,
          "--sample-rate", SAMPLE_RATE, "--embedder-model", "contentvec"], 1, progress)
    say(2, 0.0)
    _run(["train", "--model-name", name, "--vocoder", "HiFi-GAN", "--save-every-epoch", max(10, epochs // 10),
          "--save-only-latest", "--total-epoch", epochs, "--sample-rate", SAMPLE_RATE, "--batch-size", batch_size,
          "--gpu", 0, "--pretrained", "--index-algorithm", "Auto"], 2, progress, epochs=epochs)
    say(3, None)
    _run(["index", "--model-name", name, "--index-algorithm", "Auto"], 3, progress)
    return publish(name)


def publish(name):
    """The newest weights and the index from Applio's logs, as voices/<name>.pth and voices/<name>.index."""
    logs = os.path.join(APPLIO, "logs", name)
    weights = sorted(glob.glob(os.path.join(logs, f"{name}*.pth")) + glob.glob(os.path.join(APPLIO, "logs", f"{name}*.pth")),
                     key=os.path.getmtime)
    weights = [w for w in weights if not os.path.basename(w).startswith(("G_", "D_"))]
    index = sorted(glob.glob(os.path.join(logs, "*.index")), key=os.path.getmtime)
    if not weights:
        raise RuntimeError(f"no trained weights in {logs}")
    os.makedirs(VOICES, exist_ok=True)
    pth = os.path.join(VOICES, name + ".pth")
    shutil.copy(weights[-1], pth)
    out_index = None
    if index:
        out_index = os.path.join(VOICES, name + ".index")
        shutil.copy(index[-1], out_index)
    return pth, out_index


def convert(name, wav_in, wav_out, pitch=0):
    """Speak a recording with a trained voice (to try it): Applio's infer."""
    pth = os.path.join(VOICES, name + ".pth")
    index = os.path.join(VOICES, name + ".index")
    _run(["infer", "--input-path", wav_in, "--output-path", wav_out, "--pth-path", pth,
          "--index-path", index if os.path.exists(index) else "", "--pitch", pitch, "--f0-method", "rmvpe",
          "--index-rate", 0.6, "--protect", 0.33, "--export-format", "WAV"], 0, None)
    return wav_out
