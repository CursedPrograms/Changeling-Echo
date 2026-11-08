@echo off
rem run.bat - Changeling Echo. The first time: a Python 3.12 venv, Applio (cloned; its training engine with
rem PyTorch for CUDA 12.8, a few GB), Echo's own requirements and the two Piper voices. Then the window.
rem The training models (about 740 MB) come from the window's "Get the models" button, when you want them.
setlocal
cd /d "%~dp0"
set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" (
    echo Creating venv ...
    py -3.12 -m venv venv || goto :fail
    "%PY%" -m pip install -q --upgrade pip uv || goto :fail
)
if not exist "Applio\core.py" (
    echo Getting Applio ...
    git clone --depth 1 https://github.com/IAHispano/Applio.git Applio || goto :fail
)
if not exist "venv\applio.installed" (
    echo Installing Applio's training engine, a few GB, once ...
    "%PY%" -m uv pip install -r Applio\requirements-engine.txt --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match --python "%PY%" || goto :fail
    echo done> venv\applio.installed
)
fc /b requirements.txt venv\requirements.installed >nul 2>&1
if errorlevel 1 (
    "%PY%" -m pip install -q -r requirements.txt || goto :fail
    copy /y requirements.txt venv\requirements.installed >nul
)
call :voice en_US-amy-medium en/en_US/amy/medium || goto :fail
call :voice en_US-ryan-medium en/en_US/ryan/medium || goto :fail
"%PY%" app.py %*
if errorlevel 1 pause
exit /b

:voice
if exist "piper_voices\%1.onnx" exit /b 0
echo Downloading the Piper voice %1, about 60 MB, once ...
if not exist piper_voices mkdir piper_voices
curl -L --fail -o "piper_voices\%1.onnx" "https://huggingface.co/rhasspy/piper-voices/resolve/main/%2/%1.onnx" || exit /b 1
curl -L --fail -o "piper_voices\%1.onnx.json" "https://huggingface.co/rhasspy/piper-voices/resolve/main/%2/%1.onnx.json" || exit /b 1
exit /b 0

:fail
echo Setup failed: Changeling Echo needs Python 3.12, git, and an NVIDIA GPU for training.
pause
exit /b 1
