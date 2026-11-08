#!/usr/bin/env bash
# run.sh - Changeling Echo. The first time: a Python 3.12 venv, Applio (cloned; its training engine with
# PyTorch for CUDA 12.8, a few GB), Echo's own requirements and the two Piper voices. Then the window.
# The training models (about 740 MB) come from the window's "Get the models" button, when you want them.
set -e
cd "$(dirname "$0")"
pick() { if [ -x venv/Scripts/python.exe ]; then PY=venv/Scripts/python.exe; else PY=venv/bin/python; fi; }
pick
if [ ! -x "$PY" ]; then
    echo "Creating venv ..."
    if command -v py >/dev/null 2>&1; then py -3.12 -m venv venv; else python3.12 -m venv venv; fi
    pick
    "$PY" -m pip install -q --upgrade pip uv
fi
[ -f Applio/core.py ] || git clone --depth 1 https://github.com/IAHispano/Applio.git Applio
if [ ! -f venv/applio.installed ]; then
    echo "Installing Applio's training engine, a few GB, once ..."
    "$PY" -m uv pip install -r Applio/requirements-engine.txt --extra-index-url https://download.pytorch.org/whl/cu128 \
        --index-strategy unsafe-best-match --python "$PY"
    echo done > venv/applio.installed
fi
if ! cmp -s requirements.txt venv/requirements.installed; then
    "$PY" -m pip install -q -r requirements.txt
    cp requirements.txt venv/requirements.installed
fi
voice() {  # name path
    [ -f "piper_voices/$1.onnx" ] && return
    echo "Downloading the Piper voice $1, about 60 MB, once ..."
    mkdir -p piper_voices
    for ext in .onnx .onnx.json; do
        curl -L --fail -o "piper_voices/$1$ext" "https://huggingface.co/rhasspy/piper-voices/resolve/main/$2/$1$ext"
    done
}
voice en_US-amy-medium en/en_US/amy/medium
voice en_US-ryan-medium en/en_US/ryan/medium
exec "$PY" app.py "$@"
