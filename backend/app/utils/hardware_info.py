
import time
import psutil, cpuinfo, shutil, os, torch, re
import pynvml as nv
from pathlib import Path
import winreg
from typing import Optional
import wmi

# --- tables (références NVIDIA) ----------------------------
CUDA_PER_SM = {  # CC_major : (cuda_cores, tensor_cores)
    7: (64, 8),   # Turing SM 7.5 => RTX 20xx, Quadro RTX
    8: (128, 4),  # Ampere SM 8.x => RTX 30xx, A100
    9: (128, 4),  # Ada Lovelace SM 9 => RTX 40xx
    9: (128, 4),  # Hopper SM 9.x => H100, L40
}

TC_OPS = {       # précision : (ops_per_TC_per_clk, requires_CC_min)
    "fp16": (256*2, 7),   # 256 FMA = 512 FLOP
    "bf16": (256*2, 8),   # idem (introduit avec Ampere)
}


def cuda_runtime_available() -> bool:
    return torch.cuda.is_available()


def _env_cuda_path() -> str | None:
    for key, val in os.environ.items():
        if key.startswith(("CUDA_PATH", "CUDA_HOME")):
            if Path(val, "bin", "nvcc.exe").exists():
                return val
    return None

def _registry_cuda_path() -> str | None:
    root = r"SOFTWARE\NVIDIA Corporation\GPU Computing Toolkit\CUDA"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root) as h:
            # récupérer la sous-clé de plus haute version (v12.9 > v11.8)
            versions = []
            i = 0
            while True:
                sub = winreg.EnumKey(h, i);  i += 1
                versions.append(sub)
    except OSError:
        return None
    versions.sort(reverse=True, key=lambda s: list(map(int, re.findall(r'\d+', s))))
    for v in versions:
        try:
            with winreg.OpenKey(h, v) as hk:
                install, _ = winreg.QueryValueEx(hk, "InstallDir")
                if Path(install, "bin", "nvcc.exe").exists():
                    return install
        except OSError:
            continue
    return None

def _default_cuda_path() -> str | None:
    base = Path("C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA") 
    if base.exists():
        candidates = sorted(base.glob("v*"), reverse=True)
        for p in candidates:
            if (p / "bin" / "nvcc.exe").exists():
                return str(p)
    return None

def find_cuda_toolkit() -> str | None:
    return (_env_cuda_path() or
            _registry_cuda_path() or
            _default_cuda_path())

def get_cuda_info():
    runtime_ok = cuda_runtime_available()
    toolkit    = find_cuda_toolkit()
    return {
        "cuda_runtime_available": runtime_ok,
        "cuda_toolkit_found": bool(toolkit),
        "cuda_toolkit_path": toolkit,
    }

def _nvml_gpus():
    """Retourne une liste de dictionnaires décrivant chaque GPU détecté par NVML."""
    nv.nvmlInit()
    gpus = []
    for idx in range(nv.nvmlDeviceGetCount()):
        handle       = nv.nvmlDeviceGetHandleByIndex(idx)
        name         = nv.nvmlDeviceGetName(handle)
        mem_info     = nv.nvmlDeviceGetMemoryInfo(handle)
        gpus.append({
            "id": idx,
            "handle": handle,
            "name": name,
            "vram_total_mb": mem_info.total / 2**20,
            "vram_free_mb":  mem_info.free  / 2**20,
        })
    return gpus


def _select_best_gpu(gpus):
    """Sélectionne le GPU avec le plus de VRAM totale."""
    return max(gpus, key=lambda g: g["vram_total_mb"]) if gpus else None



def get_whole_hardware_info():
    """Renvoie un instantané complet (RAM, CPU, disque, GPU, CUDA)."""

    # RAM
    vm = psutil.virtual_memory()
    total_ram_gb  = vm.total  / 2**30
    avail_ram_gb  = vm.available / 2**30
    print("Total RAM (GB):", total_ram_gb)
    print("Available RAM (GB):", avail_ram_gb)

    # Disque du dossier courant
    du = psutil.disk_usage(os.getcwd())
    disk_total_gb = du.total  / 2**30
    disk_avail_gb = du.free   / 2**30

    # CPU
    cpu_model = cpuinfo.get_cpu_info().get("brand_raw", "Unknown")

    # GPU (via NVML)
    gpus = _nvml_gpus()
    if gpus:
        best = _select_best_gpu(gpus)
        gpu_model       = best["name"]
        gpu_vram_total  = best["vram_total_mb"]
        gpu_vram_free   = best["vram_free_mb"]
    else:
        gpu_model = gpu_vram_total = gpu_vram_free = None

    # CUDA
    cuda_info = get_cuda_info()

    return (total_ram_gb, avail_ram_gb, cpu_model, gpu_model,
            gpu_vram_total, gpu_vram_free, disk_total_gb, disk_avail_gb,
            cuda_info["cuda_runtime_available"], cuda_info["cuda_toolkit_path"])



def get_current_available_hardware_info():
    """Renvoie la RAM, le disque et la VRAM dispo à l'instant T."""

    avail_ram_gb = psutil.virtual_memory().available / 2**30
    disk_avail_gb = psutil.disk_usage(os.getcwd()).free / 2**30

    gpus = _nvml_gpus()
    if gpus:
        best = _select_best_gpu(gpus)
        gpu_vram_free = best["vram_free_mb"]
    else:
        gpu_vram_free = None

    return avail_ram_gb, disk_avail_gb, gpu_vram_free


def get_static_hardware_info():
    """Renvoie le matériel statique (RAM totale, CPU, GPU, disque)."""

    total_ram_gb  = psutil.virtual_memory().total / 2**30
    disk_total_gb = psutil.disk_usage(os.getcwd()).total / 2**30
    cpu_model     = cpuinfo.get_cpu_info().get("brand_raw", "Unknown")

    gpus = _nvml_gpus()
    if gpus:
        best = _select_best_gpu(gpus)
        gpu_model      = best["name"]
        gpu_vram_total = best["vram_total_mb"]
    else:
        gpu_model = gpu_vram_total = None


    # CUDA
    cuda_info = get_cuda_info()

    return (total_ram_gb, cpu_model, gpu_model, gpu_vram_total,
            disk_total_gb, cuda_info["cuda_runtime_available"],
            cuda_info["cuda_toolkit_path"])



def warm_up_gpu(device_id: int, seconds: float = 1.0):
    """Charge simple pour monter le GPU à sa fréquence boost."""
    torch.cuda.set_device(device_id)
    a = torch.randn(4096, 4096, device="cuda")
    b = torch.randn(4096, 4096, device="cuda")
    end = time.time() + seconds
    while time.time() < end:
        _ = torch.matmul(a, b)
    torch.cuda.synchronize()

def _cpu_perf_units():
    freq = psutil.cpu_freq().max or psutil.cpu_freq().current or 2500  # MHz
    cores = psutil.cpu_count(logical=False) or 4
    return (cores * freq / 1000)

def _pcie_capacity(handle):
    nv.nvmlInit()
    gen   = nv.nvmlDeviceGetMaxPcieLinkGeneration(handle)
    width = nv.nvmlDeviceGetMaxPcieLinkWidth(handle)
    return gen * width



#  Pondérations du score global d'inférence (somme = 1)
WEIGHTS_INFERENCE = {
    "gpu_compute":   0.40,  # puissance Tensor (BF16/FP16)
    "gpu_bw":        0.30,  # bande‑passante mémoire
    "gpu_vram":      0.15,  # capacité VRAM
    "cpu_single":    0.05,  # fréquence × cœurs
    "sys_ram":       0.05,  # RAM système
    "pcie":          0.05,  # bus d’E/S
}

#  Facteurs de normalisation
NORM_INFERENCE = {
    "tflops":   80,   # 80 TFLOPS FP16
    "bandwidth":500,  # 500 GB/s – au‑delà le modèle 7B n’est plus limité
    "vram":     12,   # 12 GB suffisent pour 7B INT4
    "cpu_ghz":  3.6,  # 3,6 GHz monocœur moderne
    "ram":      24,   # 24 GB pour KV‑cache confortable + multi-tasking à l'aise
    "pcie":     32,   # Gen3 ×16 ou Gen4 ×8
}

FINETUNE_WEIGHTS = {
    "gpu_compute": 0.35,
    "gpu_vram":    0.45,
    "gpu_bw":      0.10,
    "sys_ram":     0.05,
    "pcie":        0.05,
}

FINETUNE_NORM = {
    "tflops":   600,   # gros entraînements
    "vram":     96,    # 2×48 GB
    "bandwidth":1200,  # 1.2 TB/s H100
    "ram":      64,    # 64 GB host
    "pcie":     32,    # Gen3×16
}


def get_hardware_eval_for_NVIDIA_CUDA():
    """Calcule les métriques de perf théoriques pour le meilleur GPU NVIDIA."""
    cuda_info = get_cuda_info()
    if not cuda_info["cuda_runtime_available"]:
        raise RuntimeError("CUDA runtime not available. Ensure you have CUDA 12.x installed for your NVIDIA GPU. Contact erudi team for support.")

    gpus = _nvml_gpus()
    if not gpus:
        raise RuntimeError("No NVIDIA GPU detected by NVML.")

    best = _select_best_gpu(gpus)
    handle     = best["handle"]
    device_id  = best["id"]

    # Réveil du GPU → montée en fréquence
    try:
        warm_up_gpu(device_id, 1.0)
    except Exception as e:
        raise RuntimeError(f"Failed to warm up GPU {best['name']}: {e}")

    # Horloges et bus
    sm_clock_ghz  = nv.nvmlDeviceGetClockInfo(handle, nv.NVML_CLOCK_SM)   / 1e3
    mem_clock_mhz = nv.nvmlDeviceGetClockInfo(handle, nv.NVML_CLOCK_MEM)       # MHz
    bus_bits      = nv.nvmlDeviceGetMemoryBusWidth(handle)
    bandwidth_gbs = 2 * mem_clock_mhz / 1e3 * bus_bits / 8                    # GB/s

    # Get CPU info 
    cpu_units = _cpu_perf_units()

    # Propriétés PyTorch
    props             = torch.cuda.get_device_properties(device_id)
    sm_count          = props.multi_processor_count
    cores_sm, tc_sm   = CUDA_PER_SM.get(props.major, (64, 0))

    fp32_tflops = 2 * sm_count * cores_sm * sm_clock_ghz
    tensor_perf = {
        p: (sm_count * tc_sm * ops * sm_clock_ghz / 1e3) if props.major >= need else 0
        for p, (ops, need) in TC_OPS.items()
    }

    # Performances hors-GPU
    sys_ram_gb   = psutil.virtual_memory().total / 2**30
    cpu_units    = _cpu_perf_units()
    pcie_units   = _pcie_capacity(handle)

    vram_eff_mb = best["vram_total_mb"]

    # normalisation
    C = tensor_perf.get("bf16", tensor_perf.get("fp16", 0)) / NORM_INFERENCE["tflops"]
    B = bandwidth_gbs / NORM_INFERENCE["bandwidth"]
    V = (vram_eff_mb/1024) / NORM_INFERENCE["vram"]
    R = sys_ram_gb / NORM_INFERENCE["ram"]
    P = cpu_units / (NORM_INFERENCE["cpu_ghz"] * 12)  # 12 cores ref.
    I = pcie_units / NORM_INFERENCE["pcie"]

    global_inference_score = 100 * (WEIGHTS_INFERENCE["gpu_compute"] * C + WEIGHTS_INFERENCE["gpu_bw"] * B + WEIGHTS_INFERENCE["gpu_vram"] * V +
        WEIGHTS_INFERENCE["cpu_single"] * P + WEIGHTS_INFERENCE["sys_ram"] * R + WEIGHTS_INFERENCE["pcie"] * I)
    
    Cf = tensor_perf.get("bf16", tensor_perf.get("fp16",0)) / FINETUNE_NORM["tflops"]
    Vf = (vram_eff_mb/1024) / FINETUNE_NORM["vram"]
    Bf = bandwidth_gbs / FINETUNE_NORM["bandwidth"]
    Rf = sys_ram_gb / FINETUNE_NORM["ram"]
    If = I

    global_finetuning_score = 100*(FINETUNE_WEIGHTS["gpu_compute"]*Cf + FINETUNE_WEIGHTS["gpu_vram"]*Vf +
        FINETUNE_WEIGHTS["gpu_bw"]*Bf + FINETUNE_WEIGHTS["sys_ram"]*Rf +
        FINETUNE_WEIGHTS["pcie"]*If)

    labels = ["Amazing", "Excellent", "Very High", "High", "Good", "Medium", "Bad", "Very Bad", "Poor", "Terrible"]
    def label(score):
        if score >= 90: return labels[0]
        elif score >= 80: return labels[1]
        elif score >= 70: return labels[2]
        elif score >= 60: return labels[3]
        elif score >= 50: return labels[4]
        elif score >= 40: return labels[5]
        elif score >= 30: return labels[6]
        elif score >= 20: return labels[7]
        elif score >= 10: return labels[8]
        else: return labels[9]


    # Rating GPU only
    score_gpu = 100 * (0.375 * Cf + 0.125 * Bf + 0.5 * Vf)
    print(f"GPU score: {score_gpu:.2f} ({label(score_gpu)})")

    # Rating CPU only
    score_cpu = P * 100
    print(f"CPU score: {score_cpu:.2f} ({label(score_cpu)})")


    (total_ram_gb, cpu_model, gpu_model, gpu_vram_total,
            disk_total_gb, cuda_available,
            cuda_path) = get_static_hardware_info()
    disk_avail_gb = disk_avail_gb = psutil.disk_usage(os.getcwd()).free / 2**30
    avail_ram_gb = psutil.virtual_memory().available / 2**30

    return {
        "disk_total_gb":    round(disk_total_gb, 1),
        "disk_avail_gb":    round(disk_avail_gb, 1),
        "available_ram_gb": round(avail_ram_gb, 1),
        "cpu_model":        cpu_model,
        "gpu_name":          best["name"],
        "gpu_index":         device_id,
        "vram_total_gb":     round(best["vram_total_mb"] / 1024, 1),
        "sm_clock_ghz":      round(sm_clock_ghz, 3),
        "mem_clock_mhz":     mem_clock_mhz,
        "bus_width_bits":    bus_bits,
        "mem_bandwidth_gbs": round(bandwidth_gbs, 1),
        "compute_cap":       f"{props.major}.{props.minor}",
        "sm_count":          sm_count,
        "cuda_cores_total":  sm_count * cores_sm,
        "fp32_tflops":       round(fp32_tflops, 2),
        "tensor_tflops":     {k: round(v, 2) for k, v in tensor_perf.items()},
        "system_ram_gb":     round(psutil.virtual_memory().total / 2**30, 1),
        "cpu_perf_units":    round(cpu_units, 1),
        "pcie_perf_units":   round(pcie_units, 1),
        "cuda_runtime_available": cuda_info["cuda_runtime_available"],
        "cuda_toolkit_path": cuda_info["cuda_toolkit_path"],
        "global_inference_score": global_inference_score,
        "global_inference_label": label(global_inference_score),
        "global_finetuning_score": global_finetuning_score,
        "global_finetuning_label": label(global_finetuning_score),
        "cpu_score": score_cpu,
        "gpu_score": score_gpu,
    }

if __name__ == "__main__":
    print("Hardware evaluation:" , get_hardware_eval_for_NVIDIA_CUDA())