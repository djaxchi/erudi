# Erudi

**Run local AI models on your machine — no cloud, no subscription, no data leaving your device.**

Erudi is a desktop application that lets you download, run, and chat with open-source language models entirely offline. It automatically detects your hardware and routes inference to the best available backend: NVIDIA GPU (CUDA), Apple Silicon (MLX), or CPU.

---

## Features

- **Local inference** — models run on your hardware via [llama.cpp](https://github.com/ggerganov/llama.cpp)
- **Automatic hardware detection** — picks CUDA, MLX, or CPU at startup
- **Model library** — download and convert HuggingFace models in one click
- **Knowledge Base** — attach PDF documents to a model for RAG (retrieval-augmented generation)
- **Conversation memory** — short-term, middle-term (semantic), and long-term memory per conversation
- **Fully offline** — after initial model download, no internet connection required

---

## Platform Support

| Platform | Backend | Status |
|---|---|---|
| Windows (NVIDIA GPU) | CUDA via llama-server | ✅ |
| Windows (no GPU) | CPU via llama-server | ✅ |
| macOS Apple Silicon | MLX | 🚧 In progress |
| macOS Intel | CPU via llama-server | 🚧 In progress |
| Linux (NVIDIA GPU) | CUDA via llama-server | 🚧 Planned |
| Linux (CPU) | CPU via llama-server | 🚧 Planned |

---

## Getting Started (Development)

### Prerequisites

- **Node.js** >= 18
- **Python** >= 3.11
- **Git**
- Platform-specific: CUDA 12.1 toolkit (Windows GPU), Xcode CLI tools (macOS)

### 1. Clone the repository

```bash
git clone https://github.com/your-org/erudi.git
cd erudi
```

### 2. Set up the backend

Pick the script for your platform:

| Platform | Script |
|---|---|
| macOS Apple Silicon | `bash scripts/dev/backend/setup-mac-silicon.sh` |
| macOS Intel | `bash scripts/dev/backend/setup-mac-intel.sh` |
| Windows CUDA 12.1 | `.\scripts\dev\backend\setup-win-cuda-121.ps1` |
| Windows CPU | `.\scripts\dev\backend\setup-win-cpu.ps1` |
| Linux CUDA 12.1 | `bash scripts/dev/backend/setup-linux-cuda-121.sh` |
| Linux CPU | `bash scripts/dev/backend/setup-linux-cpu.sh` |

### 3. Build llama.cpp

The inference engine needs to be compiled for your platform:

```bash
# macOS Apple Silicon
bash scripts/dev/backend/build-llamacpp-cpu-macos-silicon.sh

# macOS Intel
bash scripts/dev/backend/build-llamacpp-cpu-macos-x86.sh

# Windows CUDA — run in PowerShell
.\scripts\dev\backend\build-llamacpp-cuda-win.ps1
```

### 4. Start the app

**Terminal 1 — Backend:**
```bash
cd backend
source venv/bin/activate        # macOS/Linux
# or: .\venv\Scripts\Activate   # Windows
python run.py
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm install
npm start
```

The app opens automatically. The backend runs on `http://127.0.0.1:8765` by default.

---

## Building for Distribution

### Windows (NVIDIA GPU)

```powershell
.\scripts\build\build-win-cuda-121.ps1
```

Output: `frontend/out/installer/Erudi Setup 1.0.0.exe`

### macOS

> macOS build script is in progress. See [`docs/macos-build-readiness.md`](docs/macos-build-readiness.md) for current status.

---

## Project Structure

```
erudi/
├── backend/                  # Python FastAPI backend
│   ├── src/
│   │   ├── engines/          # Hardware backends (CUDA, CPU, MLX)
│   │   ├── domains/          # API domains (conversations, llms, knowledge_base…)
│   │   └── entities/         # SQLAlchemy models
│   ├── backend.spec          # PyInstaller build spec (Windows)
│   └── run.py                # Entry point
├── frontend/                 # Electron + React frontend
│   ├── src/
│   │   ├── main.js           # Electron main process
│   │   ├── pages/            # React pages
│   │   └── components/       # React components
│   └── forge.config.js       # Electron Forge config
├── scripts/
│   ├── dev/backend/          # Dev environment setup scripts
│   └── build/                # Distribution build scripts
└── docs/                     # Architecture and build notes
```

---

## Architecture

The app has two processes:

- **Electron frontend** — React UI running in a BrowserWindow
- **Python backend** — FastAPI server (`backend.exe` / `backend` binary in production, raw `python run.py` in dev)

The backend selects an inference engine at startup:

```
macOS ARM  →  MLX_Engine   (Apple Neural Engine via MLX framework)
macOS x86  →  CPU_Engine   (llama-server, CPU only)
Windows/Linux + NVIDIA  →  CUDA_Engine  (llama-server with CUDA offload)
Windows/Linux, no GPU   →  CPU_Engine   (llama-server, CPU only)
```

All GPU inference goes through `llama-server` from llama.cpp. The bundled PyTorch is CPU-only and used only for sentence-transformers embeddings (Knowledge Base and conversation memory).

---

## Logs

| Platform | Log location |
|---|---|
| Windows | `%TEMP%\erudi-backend.log` |
| macOS / Linux | `/tmp/erudi-backend.log` |

---

## Contributing

We welcome contributions. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines, and check the open issues for good first tasks.

---

## License

[MIT](LICENSE)
