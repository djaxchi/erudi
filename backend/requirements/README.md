# Requirements configuration

For better maintainance of the packages and supported builds, the reqs have been separated folowwing needs of each system and/or hardware.

## It is built as follows :
- Entry-points
- Meta-reqs in meta/
---

`meta/base.txt`
This is the base requirements common to every version, regardless of the platform, system or hardware.

`meta/win-specs.txt`
This is the base requirements for Windows platforms, that cannot be shared with Linux or MacOS distributions.

`meta/linux-specs.txt`
This is the base requirements for Windows platforms, that cannot be shared with Linux or MacOS distributions.

`meta/mac-intel-specs.txt`
This is the old intel chips MacOS requirements that are specific to that hardware.

`meta/mac-silicon-specs.txt`
This is the latest M-Series chips MacOS requirements that are specific to that hardware.

`meta/cuda-base-specs.txt`
This is the requirements that are shared by all CUDA GPUs, regardless of their version.

`meta/cuda-118-specs.txt`
This is the requirements that are specific to CUDA-11.8 up to CUDA-12.0 GPUs. Erudi will not run for GPUs that do not support this runtime (it should not be a problem as this supports RTX 20xx and others, which are veryyy old. Older than these would not run on transformers and other similar frameworks)

`meta/cuda-121-specs.txt`
This is the requirements that are specific to CUDA-12.1+ GPUs. It is the latest stable version supported by pytorch (hence transformers and all other frameworks). It should cover every GPU so far.

`meta/cuda-linux-specs.txt`
This is the requirements that are specific to CUDA GPUs running on Linux systems.

`meta/cuda-win-specs.txt`
This is the requirements that are specific to CUDA GPUs running on Windows systems.

`meta/cpu.txt`
This is the requirements that are specific to Linux and Windows that don't have a CUDA GPU (they may have a AMD GPU but it might not be used for acceleration).
---

`requirements-win-cuda-121.txt`
This is the entry-point for the Windows CUDA-12.1+ machines. It combines:
- `meta/base.txt`
- `meta/win-specs.txt`
- `meta/cuda-base-specs.txt`
- `meta/cuda-win-specs.txt`
- `meta/cuda-121-specs.txt`

And others que j'ai la flemme de lister...