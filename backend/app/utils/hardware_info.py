
import psutil, cpuinfo, os
from pathlib import Path
from typing import Optional

# CPU-only, Linux-only version.


def get_whole_hardware_info():
    """Renvoie un instantané complet (RAM, CPU, disque). GPU/CUDA fields are None or N/A."""
    vm = psutil.virtual_memory()
    total_ram_gb  = vm.total  / 2**30
    avail_ram_gb  = vm.available / 2**30
    du = psutil.disk_usage(os.getcwd())
    disk_total_gb = du.total  / 2**30
    disk_avail_gb = du.free   / 2**30
    cpu_model = cpuinfo.get_cpu_info().get("brand_raw", "Unknown")
    # GPU/CUDA fields set to None or N/A
    return (total_ram_gb, avail_ram_gb, cpu_model, disk_total_gb, disk_avail_gb)



def get_current_available_hardware_info():
    """Renvoie la RAM et le disque dispo à l'instant T. GPU VRAM is None."""
    avail_ram_gb = psutil.virtual_memory().available / 2**30
    disk_avail_gb = psutil.disk_usage(os.getcwd()).free / 2**30
    return avail_ram_gb, disk_avail_gb


def get_static_hardware_info():
    """Renvoie le matériel statique (RAM totale, CPU, disque). GPU/CUDA fields are None or N/A."""
    total_ram_gb  = psutil.virtual_memory().total / 2**30
    disk_total_gb = psutil.disk_usage(os.getcwd()).total / 2**30
    cpu_model     = cpuinfo.get_cpu_info().get("brand_raw", "Unknown")
    return (total_ram_gb, cpu_model, disk_total_gb)

def _cpu_perf_units() -> float:
    freq = psutil.cpu_freq().max or psutil.cpu_freq().current or 2500
    cores = psutil.cpu_count(logical=False) or 4
    return (cores * freq / 1000)


def get_hardware_eval_for_linux_cpu():
    """CPU-only: returns all fields, but GPU/CUDA fields are None or N/A. Scores are based on CPU and RAM only."""
    # Get static info
    (total_ram_gb, cpu_model, disk_total_gb) = get_static_hardware_info()
    disk_avail_gb = psutil.disk_usage(os.getcwd()).free / 2**30
    avail_ram_gb = psutil.virtual_memory().available / 2**30

    # CPU performance units (cores * freq in GHz)
    cpu_units = _cpu_perf_units()
    ram_ft_req = 64 # GB
    cpu_ft_req = 56 # GHz
    ram_inf_req = 32 # GB
    cpu_inf_req = 43 # GHz

    cpu_ft_score = min(cpu_units / cpu_ft_req, 1.0) * 100
    cpu_inf_score = min(cpu_units / cpu_inf_req, 1.0) * 100
    ram_ft_score = min(total_ram_gb / ram_ft_req, 1.0) * 100
    ram_inf_score = min(total_ram_gb / ram_inf_req, 1.0) * 100

    global_inference_score = (cpu_inf_score * 0.7 + ram_inf_score * 0.3)
    global_finetuning_score = (cpu_ft_score * 0.5 + ram_ft_score * 0.5)

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

    return {
        "disk_total_gb":    round(disk_total_gb, 1),
        "disk_avail_gb":    round(disk_avail_gb, 1),
        "available_ram_gb": round(avail_ram_gb, 1),
        "cpu_model":        cpu_model,
        "system_ram_gb":    round(total_ram_gb, 1),
        "cpu_perf_units":   round(cpu_units, 1),
        "global_inference_score": round(global_inference_score, 1),
        "global_inference_label": label(global_inference_score),
        "global_finetuning_score": round(global_finetuning_score, 1),
        "global_finetuning_label": label(global_finetuning_score),
        "cpu_score": round(cpu_ft_score, 1),
    }

if __name__ == "__main__":
    print("Hardware evaluation:" , get_hardware_eval_for_linux_cpu())