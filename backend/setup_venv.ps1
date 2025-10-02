# --- setup_venv.ps1 ---
$PyTag   = "3.12"
$VenvDir = "venv"
$ReqFile = "requirements.txt"

# (Re)crée le venv
if (Get-Command deactivate -ErrorAction SilentlyContinue) { deactivate }
if (Test-Path $VenvDir) { Remove-Item -Recurse -Force $VenvDir }
py -$PyTag -m venv $VenvDir
& "$VenvDir\Scripts\Activate.ps1"

# Met pip/outils à jour
python -m pip install -U pip setuptools wheel

# Crée un requirements sans torch
$TempReq = "requirements.no-torch.txt"
Get-Content $ReqFile |
  Where-Object {$_ -notmatch '^\s*(torch|torchvision|torchaudio)\b'} |
  Set-Content $TempReq

# Installe les deps générales
pip install -r $TempReq

# Supprime torch existant (au cas où)
pip uninstall -y torch torchvision torchaudio

# Installe PyTorch CUDA 12.8
pip install --index-url https://download.pytorch.org/whl/cu128 torch torchvision torchaudio

# --- Test CUDA rapide ---
python -c "
import torch
print('torch:', torch.__version__, 'cuda libs:', torch.version.cuda)
print('cuda available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('device:', torch.cuda.get_device_name(0))
    print('capability:', torch.cuda.get_device_capability(0))
    x = torch.randn(512,512, device='cuda') @ torch.randn(512,512, device='cuda')
    torch.cuda.synchronize()
    print('matmul OK:', x.shape)
"
Write-Host '✅ Environnement prêt. Active-le avec .\venv\Scripts\Activate.ps1'
