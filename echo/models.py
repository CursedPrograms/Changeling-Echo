"""models.py - the four files training needs, and nothing else (about 740 MB).

Applio's own downloader fetches every sample rate and every extra (over 2 GB); Echo trains at 40 kHz with
HiFi-GAN, so it needs only these. Before downloading one, it looks for a copy already on this PC
(ECHO_MODEL_DIRS, then F:\\AIModels\\rvc) and copies that instead.
"""
import os
import shutil
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPLIO = os.path.join(HERE, "Applio")
BASE = "https://huggingface.co/IAHispano/Applio/resolve/main/Resources"
FILES = [   # (where it goes in Applio, where it comes from, MB)
    ("rvc/models/pretraineds/hifi-gan/f0G40k.pth", "pretrained_v2/f0G40k.pth", 70),
    ("rvc/models/pretraineds/hifi-gan/f0D40k.pth", "pretrained_v2/f0D40k.pth", 136),
    ("rvc/models/predictors/rmvpe.pt", "predictors/rmvpe.pt", 173),
    ("rvc/models/embedders/contentvec/pytorch_model.bin", "embedders/contentvec/pytorch_model.bin", 361),
    ("rvc/models/embedders/contentvec/config.json", "embedders/contentvec/config.json", 0),
]
SEARCH = [d for d in os.environ.get("ECHO_MODEL_DIRS", "").split(os.pathsep) if d] + [r"F:\AIModels\rvc"]


def missing():
    return [f for f in FILES if not os.path.exists(os.path.join(APPLIO, f[0]))]


def missing_mb():
    return sum(f[2] for f in missing())


def _local_copy(name):
    for d in SEARCH:
        for root, _, files in os.walk(d):
            if name in files:
                return os.path.join(root, name)
    return None


def fetch(progress=None):
    """Get whatever is missing: a local copy if there is one, else a download (resumes a .part)."""
    todo = missing()
    for n, (dest, remote, mb) in enumerate(todo):
        path = os.path.join(APPLIO, dest)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        local = _local_copy(os.path.basename(dest))
        if local:
            shutil.copy(local, path)
        else:
            part = path + ".part"
            have = os.path.getsize(part) if os.path.exists(part) else 0
            req = urllib.request.Request(f"{BASE}/{remote}", headers={"Range": f"bytes={have}-"} if have else {})
            with urllib.request.urlopen(req, timeout=60) as r, open(part, "ab" if have else "wb") as out:
                total = have + int(r.headers.get("Content-Length", 0))
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
                    have += len(chunk)
                    if progress and total:
                        progress(n, len(todo), have / total, os.path.basename(dest))
            os.replace(part, path)
        if progress:
            progress(n + 1, len(todo), 1.0, os.path.basename(dest))
    return len(todo)
