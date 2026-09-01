# Erudi

**Run local AI models on your machine — no cloud, no subscription, no data leaving your device.**

Erudi is a desktop application that lets you download, run, and chat with open-source language models entirely offline. It automatically detects your hardware and routes inference to the best available backend: NVIDIA GPU (CUDA), Apple Silicon (MLX), or CPU.

---

## Features

- **Local inference** — models run on your hardware via [llama.cpp](https://github.com/ggerganov/llama.cpp)
- **Automatic hardware detection** — picks CUDA, MLX, or CPU at startup
- **Model library** — download and convert Hugging Face models in one click
- **Knowledge Base** — attach PDF documents to a model for RAG (retrieval-augmented generation)
- **Conversation memory** — short-term, middle-term (semantic), and long-term memory per conversation
- **Fully offline** — after initial model download, no internet connection required

---

## Platform Support

| Platform | Backend | Status |
|---|---|---|
| Windows (NVIDIA GPU) | CUDA via `llama-server` | ✅ Supported |
| Windows (no GPU) | CPU via `llama-server` | ✅ Supported |
| macOS Apple Silicon (macOS 14+) | MLX | ✅ Supported |
| Linux (NVIDIA GPU) | CUDA via `llama-server` | ✅ Supported |
| Linux (CPU) | CPU via `llama-server` | 🚧 In progress |

---

## Getting Started (Development)

### Prerequisites

- **Node.js** >= 18
- **Python** >= 3.11
- **Git**
- Platform-specific requirements:
  - CUDA 12.1 toolkit for Windows with an NVIDIA GPU
  - Xcode Command Line Tools for macOS

### 1. Clone the repository

```bash
git clone https://github.com/erudi-app/erudi.git
cd erudi
```

### 2. Set up the backend

Run the setup script for your platform:

| Platform | Script |
|---|---|
| macOS Apple Silicon | `bash scripts/dev/backend/setup-mac-silicon.sh` |
| Windows CUDA 12.1 | `.\scripts\dev\backend\setup-win-cuda-121.ps1` |
| Windows CPU | `.\scripts\dev\backend\setup-win-cpu.ps1` |
| Linux CUDA 12.1 | `bash scripts/dev/backend/setup-linux-cuda-121.sh` |
| Linux CPU | `bash scripts/dev/backend/setup-linux-cpu.sh` |

### 3. Build llama.cpp

The inference engine must be compiled for your platform:

```bash
# macOS Apple Silicon
bash scripts/dev/backend/build-llamacpp-cpu-macos-silicon.sh

# Linux CPU
bash scripts/dev/backend/build-llamacpp-cpu-linux.sh

# Linux CUDA
bash scripts/dev/backend/build-llamacpp-cuda-linux.sh
```

On Windows, run one of the following commands in PowerShell:

```powershell
# Windows CPU
.\scripts\dev\backend\build-llamacpp-cpu-win.ps1

# Windows CUDA
.\scripts\dev\backend\build-llamacpp-cuda-win.ps1
```

### 4. Start the app

Start the backend in the first terminal:

```bash
cd backend
source venv/bin/activate        # macOS/Linux
# Windows: .\venv\Scripts\Activate
python run.py
```

Start the frontend in a second terminal:

```bash
cd frontend
npm install
npm start
```

The app opens automatically. The backend runs on `http://127.0.0.1:27182` by default. The port number 27182 corresponds to the first digits of *e*.

Every environment variable read by the backend, including `HF_TOKEN` for gated models, `ERUDI_FORCE_CPU`, and `ERUDI_LOG_LEVEL`, is documented in [`backend/.env.example`](backend/.env.example). Copy it to the git-ignored `backend/.env` file if you need custom values.

---

## Building for Distribution

### Windows (NVIDIA GPU)

```powershell
.\scripts\build\build-win-cuda-121.ps1
```

The installer is generated at:

```text
frontend/out/installer/Erudi Setup <version>.exe
```

### macOS

> The macOS build script is in progress. See [`docs/macos-build-readiness.md`](docs/macos-build-readiness.md) for the current status.

---

## Project Structure

```text
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
│   ├── dev/backend/          # Development environment setup scripts
│   └── build/                # Distribution build scripts
└── docs/                     # Architecture and build notes
```

---

## Architecture

The app has two processes:

- **Electron frontend** — React UI running in a `BrowserWindow`
- **Python backend** — FastAPI server running as `backend.exe` or a `backend` binary in production, and through `python run.py` in development

The backend selects an inference engine at startup:

```text
macOS ARM                 → MLX_Engine  (MLX framework)
macOS x86                 → CPU_Engine  (llama-server, CPU only)
Windows/Linux + NVIDIA    → CUDA_Engine (llama-server with CUDA offload)
Windows/Linux, no NVIDIA  → CPU_Engine  (llama-server, CPU only)
```

All inference engines run an OpenAI-compatible HTTP server in a child process and communicate with it through `http://127.0.0.1:<port>/v1/chat/completions`. Windows and Linux NVIDIA backends and the CPU fallback use `llama-server` from llama.cpp. macOS Apple Silicon uses `mlx_vlm.server` for vision and tool calling. The bundled PyTorch distribution is CPU-only and is used exclusively for sentence-transformers embeddings in the Knowledge Base and conversation memory.

---

## Logs

| Platform | Log location |
|---|---|
| Windows | `%TEMP%\erudi-backend.log` |
| macOS / Linux | `/tmp/erudi-backend.log` |

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines and check the open issues for good first tasks.

---

## License

Erudi is licensed under the [MIT License](LICENSE).
