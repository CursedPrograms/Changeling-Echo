# run.ps1 - Changeling Echo. The first time: a Python 3.12 venv, Applio (cloned; its training engine with
# PyTorch for CUDA 12.8, a few GB), Echo's own requirements and the two Piper voices. Then the window.
# The training models (about 740 MB) come from the window's "Get the models" button, when you want them.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$Py = Join-Path $PSScriptRoot 'venv\Scripts\python.exe'
function Fail($msg) { Write-Host "Setup failed: $msg"; Read-Host 'Press Enter'; exit 1 }
if (-not (Test-Path $Py)) {
    Write-Host 'Creating venv ...'
    & py -3.12 -m venv venv
    if ($LASTEXITCODE) { Fail 'Changeling Echo needs Python 3.12.' }
    & $Py -m pip install -q --upgrade pip uv
}
if (-not (Test-Path 'Applio/core.py')) {
    Write-Host 'Getting Applio ...'
    & git clone --depth 1 https://github.com/IAHispano/Applio.git Applio
    if ($LASTEXITCODE) { Fail 'could not clone Applio (is git installed?).' }
}
if (-not (Test-Path 'venv/applio.installed')) {
    Write-Host "Installing Applio's training engine, a few GB, once ..."
    & $Py -m uv pip install -r Applio/requirements-engine.txt --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match --python $Py
    if ($LASTEXITCODE) { Fail "could not install Applio's engine." }
    Set-Content -Path 'venv/applio.installed' -Value 'done' -Encoding utf8
}
$stamp = 'venv/requirements.installed'
if (-not (Test-Path $stamp) -or (Get-FileHash requirements.txt).Hash -ne (Get-FileHash $stamp).Hash) {
    & $Py -m pip install -q -r requirements.txt
    if ($LASTEXITCODE) { Fail 'pip could not install the requirements.' }
    Copy-Item requirements.txt $stamp -Force
}
foreach ($v in @(@('en_US-amy-medium', 'en/en_US/amy/medium'), @('en_US-ryan-medium', 'en/en_US/ryan/medium'))) {
    $name, $path = $v
    if (-not (Test-Path "piper_voices/$name.onnx")) {
        Write-Host "Downloading the Piper voice $name, about 60 MB, once ..."
        New-Item -ItemType Directory -Force piper_voices | Out-Null
        foreach ($ext in @('.onnx', '.onnx.json')) {
            & curl.exe -L --fail -o "piper_voices/$name$ext" "https://huggingface.co/rhasspy/piper-voices/resolve/main/$path/$name$ext"
            if ($LASTEXITCODE) { Fail "could not download $name$ext." }
        }
    }
}
& $Py app.py @args
if ($LASTEXITCODE) { Read-Host 'Press Enter' }
