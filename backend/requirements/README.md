# Erudi Backend Requirements Structure# Requirements configuration



## 📂 Directory StructureFor better maintainance of the packages and supported builds, the reqs have been separated folowwing needs of each system and/or hardware.



```## It is built as follows :

requirements/- Entry-points

├── README.md                    # This file- Meta-reqs in meta/

├── entrypoints/                 # Entry point files for installations---

│   ├── mac-silicon.txt          # Dev: Mac Silicon (M1/M2/M3+)

│   ├── mac-silicon-prod.txt     # Prod: Mac Silicon`meta/base.txt`

│   ├── mac-intel.txt            # Dev: Mac IntelThis is the base requirements common to every version, regardless of the platform, system or hardware.

│   ├── mac-intel-prod.txt       # Prod: Mac Intel

│   ├── linux-cpu.txt            # Dev: Linux CPU`meta/win-specs.txt`

│   ├── linux-cpu-prod.txt       # Prod: Linux CPUThis is the base requirements for Windows platforms, that cannot be shared with Linux or MacOS distributions.

│   ├── linux-cuda-121.txt       # Dev: Linux CUDA 12.1

│   ├── linux-cuda-121-prod.txt  # Prod: Linux CUDA 12.1`meta/linux-specs.txt`

│   ├── linux-cuda-118.txt       # Dev: Linux CUDA 11.8This is the base requirements for Windows platforms, that cannot be shared with Linux or MacOS distributions.

│   ├── linux-cuda-118-prod.txt  # Prod: Linux CUDA 11.8

│   ├── win-cpu.txt              # Dev: Windows CPU`meta/mac-intel-specs.txt`

│   ├── win-cpu-prod.txt         # Prod: Windows CPUThis is the old intel chips MacOS requirements that are specific to that hardware.

│   ├── win-cuda-121.txt         # Dev: Windows CUDA 12.1

│   ├── win-cuda-121-prod.txt    # Prod: Windows CUDA 12.1`meta/mac-silicon-specs.txt`

│   ├── win-cuda-118.txt         # Dev: Windows CUDA 11.8This is the latest M-Series chips MacOS requirements that are specific to that hardware.

│   └── win-cuda-118-prod.txt    # Prod: Windows CUDA 11.8

├── meta/                        # Modular requirement files`meta/cuda-base-specs.txt`

│   ├── base.txt                 # Core dependencies (FastAPI, SQLAlchemy, etc.)This is the requirements that are shared by all CUDA GPUs, regardless of their version.

│   ├── dev.txt                  # Development tools (pytest, black, ruff, mypy)

│   ├── cpu.txt                  # CPU-specific packages`meta/cuda-118-specs.txt`

│   ├── cuda-base-specs.txt      # Base CUDA packagesThis is the requirements that are specific to CUDA-11.8 up to CUDA-12.0 GPUs. Erudi will not run for GPUs that do not support this runtime (it should not be a problem as this supports RTX 20xx and others, which are veryyy old. Older than these would not run on transformers and other similar frameworks)

│   ├── cuda-118-specs.txt       # CUDA 11.8 specific

│   ├── cuda-121-specs.txt       # CUDA 12.1 specific`meta/cuda-121-specs.txt`

│   ├── cuda-linux-specs.txt     # CUDA Linux specificThis is the requirements that are specific to CUDA-12.1+ GPUs. It is the latest stable version supported by pytorch (hence transformers and all other frameworks). It should cover every GPU so far.

│   ├── cuda-win-specs.txt       # CUDA Windows specific

│   ├── linux-specs.txt          # Linux specific`meta/cuda-linux-specs.txt`

│   ├── mac-intel-specs.txt      # Mac Intel specificThis is the requirements that are specific to CUDA GPUs running on Linux systems.

│   ├── mac-silicon-specs.txt    # Mac Silicon specific (MLX)

│   └── win-specs.txt            # Windows specific`meta/cuda-win-specs.txt`

└── freezes/                     # Frozen requirements for reproducibilityThis is the requirements that are specific to CUDA GPUs running on Windows systems.

    └── v0.1.0-win-cuda-121-freeze.txt

````meta/cpu.txt`

This is the requirements that are specific to Linux and Windows that don't have a CUDA GPU (they may have a AMD GPU but it might not be used for acceleration).

## 🎯 Usage---



### Development Installation`requirements-win-cuda-121.txt`

This is the entry-point for the Windows CUDA-12.1+ machines. It combines:

For local development with testing, linting, and debugging tools:- `meta/base.txt`

- `meta/win-specs.txt`

**Mac Silicon:**- `meta/cuda-base-specs.txt`

```bash- `meta/cuda-win-specs.txt`

pip install -r requirements/entrypoints/dev/mac-silicon.txt

```

And others que j'ai la flemme de lister...
**Linux CUDA 12.1:**
```bash
pip install -r requirements/entrypoints/dev/linux-cuda-121.txt
```

**Windows CUDA 12.1:**
```powershell
pip install -r requirements/entrypoints/dev/win-cuda-121.txt
```

### Production Installation

For production deployment with minimal dependencies:

**Mac Silicon:**
```bash
pip install -r requirements/entrypoints/prod/mac-silicon-prod.txt
```

**Linux CUDA 12.1:**
```bash
pip install -r requirements/entrypoints/prod/linux-cuda-121-prod.txt
```

**Windows CUDA 12.1:**
```powershell
pip install -r requirements/entrypoints/prod/win-cuda-121-prod.txt
```

## 🔧 Automated Setup Scripts

Use platform-specific setup scripts for automated environment configuration:

### Mac Silicon
```bash
bash scripts/dev/backend/setup-mac-silicon.sh
```

The script will prompt you to choose:
- **[1] Development**: Includes pytest, black, ruff, mypy, ipython
- **[2] Production**: Minimal dependencies only

### Linux/Windows
Similar scripts available for other platforms in `scripts/dev/backend/`

### CI/CD Mode

Scripts automatically detect CI/CD environments and default to production mode:

```bash
# Force production in CI
export INSTALL_TYPE=prod
bash scripts/dev/backend/setup-mac-silicon.sh

# Force development in CI
export INSTALL_TYPE=dev
bash scripts/dev/backend/setup-mac-silicon.sh
```

## 📦 What's Included

### Production Dependencies (`*-prod.txt`)
- **Core Framework**: FastAPI, Uvicorn
- **Database**: SQLAlchemy
- **LLM Inference**: Platform-specific (MLX, CUDA, CPU)
- **Embeddings**: Sentence Transformers, FAISS
- **Utilities**: Pydantic, python-dotenv, pypdf, tqdm
- **System**: NumPy, psutil, py-cpuinfo

### Development Dependencies (`meta/dev.txt`)
- **Testing**: pytest, pytest-asyncio, pytest-cov, httpx
- **Code Quality**: black, ruff, mypy
- **Debugging**: ipython, ipdb
- **Type Checking**: types-python-dateutil

## 🏗️ Architecture

### Modular Design

Requirements are organized in a modular way to avoid duplication:

```
entrypoints/dev/mac-silicon.txt
  ├─> entrypoints/prod/mac-silicon-prod.txt
  │     ├─> meta/base.txt (core deps)
  │     └─> meta/mac-silicon-specs.txt (MLX)
  └─> meta/dev.txt (testing tools)
```

### Benefits

1. **DRY Principle**: No duplication between dev and prod
2. **Easy Updates**: Update `base.txt` once, affects all platforms
3. **Clear Separation**: Dev tools isolated in `meta/dev.txt`
4. **Platform Flexibility**: Easy to add new platforms or CUDA versions
5. **CI/CD Ready**: Production freezes for reproducible builds

## 🚀 Best Practices

### For Developers

1. Always use development requirements during local development
2. Run tests before committing: `pytest`
3. Format code: `black .` and `ruff check .`
4. Type check: `mypy src/`

### For Production

1. Use production requirements for deployments
2. Consider creating freezes: `pip freeze > requirements/freezes/v0.x.x-freeze.txt`
3. Test prod requirements before deploying
4. Keep prod requirements minimal for security and performance

### For CI/CD

1. Set `INSTALL_TYPE=prod` environment variable
2. Use frozen requirements for reproducible builds
3. Cache virtual environments to speed up pipelines
4. Run tests with production dependencies

## 📝 Adding New Dependencies

### Core Dependency (all platforms)
Add to `meta/base.txt`

### Development Tool
Add to `meta/dev.txt`

### Platform-Specific
Add to appropriate `meta/*-specs.txt`

### New Platform
1. Create `meta/new-platform-specs.txt`
2. Create `entrypoints/prod/new-platform-prod.txt` referencing base + new specs
3. Create `entrypoints/dev/new-platform.txt` referencing prod + dev
4. Create setup script in `scripts/dev/backend/`

## 🔒 Security

- Review all dependency updates for vulnerabilities
- Use `pip-audit` to scan for known security issues
- Keep dependencies updated regularly
- Minimize production dependencies to reduce attack surface

## 📊 Maintenance

### Regular Updates
```bash
# Update all packages
pip install --upgrade -r requirements/entrypoints/dev/mac-silicon.txt

# Create new freeze
pip freeze > requirements/freezes/v0.x.x-freeze.txt
```

### Dependency Review
- Quarterly review of all dependencies
- Remove unused packages
- Check for newer stable versions
- Test thoroughly after updates
