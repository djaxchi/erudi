"""Tests for `CPU_Engine` hardware detection, scoring and GGUF conversion.

Complements `test_cpu_engine_server.py` (spawn hooks / GGUF picker / kwarg
translation) by pinning the hardware-info structure, the performance scoring
pipeline and its fallbacks, the auxiliary-file copier, and both branches of
`quant_and_save_from_hf_format` (pre-quantized copy vs. SafeTensors
conversion, including the CUDA-artifact fallbacks) with mocked llama.cpp
tools. No subprocess or model download happens anywhere in this file.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.exceptions import EngineException
from src.engines import cpu_engine as cpu_mod
from src.engines.cpu_engine import CPU_Engine

from tests.test_cuda_engine_hardware import _write_converter_script


# =====================================================================
# UNIT - get_hardware_info
# =====================================================================

@pytest.mark.unit
class TestGetHardwareInfo:

    def test_structure_and_cpu_only_gpu_block(self):
        info = CPU_Engine.get_hardware_info()
        assert info["backend_type"] == "cpu"
        assert info["gpu"]["gpu_name"] == "CPU Only"
        assert info["gpu"]["mps_supported"] is False
        assert info["gpu"]["unified_memory"] is False
        assert info["cpu"]["total_cores"] >= 1
        assert info["memory"]["total_memory_gb"] > 0
        assert info["storage"]["total_gb"] > 0
        assert info["memory"]["memory_type"] == "system"

    def test_without_psutil_falls_back_to_os_cpu_count(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "psutil", None)
        info = CPU_Engine.get_hardware_info()
        assert info["cpu"]["total_cores"] >= 1
        # Memory/disk metrics require psutil -> None without it
        assert info["memory"]["total_memory_gb"] is None
        assert info["storage"]["total_gb"] is None

    def test_detection_failure_returns_minimal_fallback(self, monkeypatch):
        def boom():
            raise RuntimeError("sysctl exploded")

        monkeypatch.setattr(cpu_mod, "get_cpu_brand", boom)
        info = CPU_Engine.get_hardware_info()
        assert info["backend_type"] == "cpu"
        assert info["cpu"]["model"] == "Unknown CPU"
        assert info["gpu"]["gpu_name"] == "CPU Only"
        assert info["memory"]["total_memory_gb"] is None

    def test_cpu_brand_overrides_generic_processor(self, monkeypatch):
        monkeypatch.setattr(cpu_mod, "get_cpu_brand", lambda: "Erudium X1")
        info = CPU_Engine.get_hardware_info()
        assert info["cpu"]["model"] == "Erudium X1"


# =====================================================================
# UNIT - warm_up_accelerator
# =====================================================================

@pytest.mark.unit
class TestWarmUp:

    def test_completes_quickly_and_returns_true(self):
        assert CPU_Engine.warm_up_accelerator(0.06) is True

    def test_failure_returns_false(self, monkeypatch):
        class BrokenClock:
            @staticmethod
            def time():
                raise RuntimeError("clock unavailable")

            sleep = staticmethod(lambda s: None)

        # Swap only cpu_engine's module-level `time` reference so the logging
        # machinery (which also uses the real time module) keeps working.
        monkeypatch.setattr(cpu_mod, "time", BrokenClock)
        assert CPU_Engine.warm_up_accelerator(0.05) is False


# =====================================================================
# UNIT - get_performance_evaluation / get_flat_hardware_data
# =====================================================================

@pytest.mark.unit
class TestPerformanceEvaluation:

    def test_scores_derived_from_hardware_info(self):
        fake_info = {
            "cpu": {"model": "Erudium X1", "total_cores": 16, "architecture": "arm64"},
            "memory": {"total_memory_gb": 64.0, "available_memory_gb": 32.0},
            "storage": {"total_gb": 1000.0, "available_gb": 500.0},
            "system": {"platform": "Darwin"},
        }
        with patch.object(CPU_Engine, "get_hardware_info", return_value=fake_info):
            result = CPU_Engine.get_performance_evaluation()

        assert result["backend_type"] == "cpu"
        assert result["gpu_name"] == "CPU Only"
        assert result["cpu_model"] == "Erudium X1"
        assert result["cpu_performance_units"] == 16
        # cpu_score = 16/64*100 = 25 ; memory = 64/128*100 = 50
        assert result["cpu_score"] == 25.0
        assert result["memory_score"] == 50.0
        # bandwidth est. = 16 * 1.5 = 24 GB/s ; disk = 500/500*100 = 100
        assert result["memory_bandwidth_gbs"] == 24.0
        assert result["performance_breakdown"]["disk_score"] == 100.0
        # inference = 25*.4 + 50*.3 + 24*.2 + 100*.1 = 39.8 -> "Medium" (>= 25)
        assert result["global_inference_score"] == pytest.approx(39.8)
        assert result["global_inference_label"] == "Medium"
        assert result["gpu_score"] == 0.0
        assert result["unified_memory"] is False

    @pytest.mark.parametrize("cores,expected_label", [
        (64, "Excellent"),  # 100*.4 + 50*.3 + 96*.2 + 100*.1 = 84.2 -> >= 70
        (1, "Medium"),      # 1.56*.4 + 50*.3 + 1.5*.2 + 100*.1 = 25.9 -> >= 25
    ])
    def test_labels_track_core_count(self, cores, expected_label):
        fake_info = {
            "cpu": {"model": "X", "total_cores": cores, "architecture": "x86_64"},
            "memory": {"total_memory_gb": 64.0, "available_memory_gb": 32.0},
            "storage": {"total_gb": 1000.0, "available_gb": 500.0},
            "system": {"platform": "Linux"},
        }
        with patch.object(CPU_Engine, "get_hardware_info", return_value=fake_info):
            result = CPU_Engine.get_performance_evaluation()
        assert result["global_inference_label"] == expected_label

    def test_none_metrics_are_coalesced_to_zero(self):
        fake_info = {
            "cpu": {"model": "X", "total_cores": None, "architecture": "x86_64"},
            "memory": {"total_memory_gb": None, "available_memory_gb": None},
            "storage": {"total_gb": None, "available_gb": None},
            "system": {"platform": "Linux"},
        }
        with patch.object(CPU_Engine, "get_hardware_info", return_value=fake_info):
            result = CPU_Engine.get_performance_evaluation()
        assert result["cpu_performance_units"] == 1
        assert result["total_memory_gb"] == 0
        assert result["performance_breakdown"]["disk_score"] == 0.0

    def test_failure_returns_core_based_fallback(self):
        with patch.object(
            CPU_Engine, "get_hardware_info", side_effect=RuntimeError("boom")
        ):
            result = CPU_Engine.get_performance_evaluation()
        assert result["backend_type"] == "cpu"
        assert result["global_inference_label"] == "Poor"
        assert result["cpu_performance_units"] >= 1
        assert result["total_memory_gb"] is None
        assert result["memory_score"] == 0.0

    def test_flat_hardware_data_delegates_to_evaluation(self):
        sentinel = {"backend_type": "cpu", "cpu_score": 12.0}
        with patch.object(
            CPU_Engine, "get_performance_evaluation", return_value=sentinel
        ):
            assert CPU_Engine.get_flat_hardware_data() is sentinel


# =====================================================================
# UNIT - _copy_auxiliary_files
# =====================================================================

@pytest.mark.unit
class TestCopyAuxiliaryFiles:

    def test_copies_configs_but_skips_weights(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "config.json").write_text("{}")
        (src / "tokenizer.model").write_bytes(b"\x00")
        (src / "weights.safetensors").write_bytes(b"\x00")
        (src / "model.gguf").write_bytes(b"\x00")
        (src / "subdir").mkdir()
        dst = tmp_path / "dst"
        dst.mkdir()

        CPU_Engine._copy_auxiliary_files(src, dst)

        assert (dst / "config.json").exists()
        assert not (dst / "tokenizer.model").exists()
        assert not (dst / "weights.safetensors").exists()
        assert not (dst / "model.gguf").exists()
        assert not (dst / "subdir").exists()


# =====================================================================
# UNIT - quant_and_save_from_hf_format
# =====================================================================

@pytest.mark.unit
class TestQuantAndSave:

    def test_missing_source_raises_filenotfound(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            CPU_Engine.quant_and_save_from_hf_format(
                tmp_path / "missing", tmp_path / "dst"
            )

    def test_pre_quantized_gguf_fast_path(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "model-q4_k_m.gguf").write_bytes(b"\x00" * 128)
        (src / "model-f16.gguf").write_bytes(b"\x00" * 128)
        (src / "config.json").write_text("{}")
        dst = tmp_path / "dst"

        CPU_Engine.quant_and_save_from_hf_format(src, dst)

        assert (dst / "model-q4_k_m.gguf").exists()
        assert not (dst / "model-f16.gguf").exists()
        assert (dst / "config.json").exists()

    def test_no_model_files_raises(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        with pytest.raises(EngineException, match="No .gguf or .safetensors"):
            CPU_Engine.quant_and_save_from_hf_format(src, tmp_path / "dst")

    def test_missing_converter_everywhere_raises(self, tmp_path, monkeypatch):
        src = tmp_path / "src"
        src.mkdir()
        (src / "model.safetensors").write_bytes(b"\x00" * 16)
        empty_install = tmp_path / "install"
        empty_install.mkdir()
        # Redirect the cuda-bin fallback into the sandbox too.
        monkeypatch.setattr(cpu_mod, "ROOT_DIR", tmp_path / "root")
        with patch.object(
            CPU_Engine, "_default_install_dir", return_value=empty_install
        ):
            with pytest.raises(EngineException, match="Converter script not found"):
                CPU_Engine.quant_and_save_from_hf_format(src, tmp_path / "dst")

    def _setup_safetensors_job(self, tmp_path, monkeypatch, *, quant_rc=0):
        src = tmp_path / "src"
        src.mkdir()
        (src / "model.safetensors").write_bytes(b"\x00" * 16)
        (src / "tokenizer.json").write_text("{}")
        dst = tmp_path / "dst"
        install = tmp_path / "install"
        _write_converter_script(install)
        # Match the platform-specific name quant_and_save_from_hf_format actually
        # looks for (cpu_engine.py: "llama-quantize.exe" if os.name == "nt" else
        # "llama-quantize") -- a POSIX-only literal here made every one of these
        # tests fail with "Quantizer binary not found" on Windows CI (#357).
        _quantizer_name = "llama-quantize.exe" if os.name == "nt" else "llama-quantize"
        (install / _quantizer_name).write_bytes(b"\x7fELF")
        monkeypatch.setattr(cpu_mod, "ROOT_DIR", tmp_path / "root")

        def fake_call(cmd):
            out = Path(cmd[-1])
            if str(out).endswith(".gguf.tmp") or str(out).endswith(".gguf"):
                out.write_bytes(b"GGUF" + b"\x00" * 64)
            # Conversion command has --outfile before the path; quantize
            # command is [bin, fp16, out_tmp, method] -> create out_tmp.
            if len(cmd) == 4 and cmd[-1] in {"q4_k_m", "q8_0"}:
                Path(cmd[2]).write_bytes(b"GGUF-Q")
            return quant_rc if cmd[-1] in {"q4_k_m", "q8_0"} else 0

        monkeypatch.setattr(cpu_mod.subprocess, "call", fake_call)
        return src, dst, install

    def test_safetensors_convert_and_quantize_success(self, tmp_path, monkeypatch):
        src, dst, install = self._setup_safetensors_job(tmp_path, monkeypatch)
        with patch.object(CPU_Engine, "_default_install_dir", return_value=install):
            CPU_Engine.quant_and_save_from_hf_format(src, dst, quantize=True, q_bits="4")
        assert (dst / "model-q4_k_m.gguf").exists()
        assert not (dst / "model-f16.gguf").exists()
        assert not (dst / "model-q4_k_m.gguf.tmp").exists()
        assert (dst / "tokenizer.json").exists()

    def test_q8_selects_q8_0_method(self, tmp_path, monkeypatch):
        src, dst, install = self._setup_safetensors_job(tmp_path, monkeypatch)
        with patch.object(CPU_Engine, "_default_install_dir", return_value=install):
            CPU_Engine.quant_and_save_from_hf_format(src, dst, quantize=True, q_bits="8")
        assert (dst / "model-q8_0.gguf").exists()

    def test_quantize_false_keeps_fp16(self, tmp_path, monkeypatch):
        src, dst, install = self._setup_safetensors_job(tmp_path, monkeypatch)
        with patch.object(CPU_Engine, "_default_install_dir", return_value=install):
            CPU_Engine.quant_and_save_from_hf_format(src, dst, quantize=False)
        assert (dst / "model-f16.gguf").exists()

    def test_conversion_failure_raises(self, tmp_path, monkeypatch):
        src, dst, install = self._setup_safetensors_job(tmp_path, monkeypatch)
        monkeypatch.setattr(cpu_mod.subprocess, "call", lambda cmd: 2)
        with patch.object(CPU_Engine, "_default_install_dir", return_value=install):
            with pytest.raises(EngineException, match="conversion failed"):
                CPU_Engine.quant_and_save_from_hf_format(src, dst)

    def test_quantize_failure_raises_and_cleans_tmp(self, tmp_path, monkeypatch):
        src, dst, install = self._setup_safetensors_job(
            tmp_path, monkeypatch, quant_rc=1
        )
        with patch.object(CPU_Engine, "_default_install_dir", return_value=install):
            with pytest.raises(EngineException, match="Quantization failed"):
                CPU_Engine.quant_and_save_from_hf_format(src, dst)
        assert not (dst / "model-q4_k_m.gguf.tmp").exists()

    def test_missing_quantizer_raises(self, tmp_path, monkeypatch):
        src, dst, install = self._setup_safetensors_job(tmp_path, monkeypatch)
        quantizer_name = "llama-quantize.exe" if os.name == "nt" else "llama-quantize"
        (install / quantizer_name).unlink()
        with patch.object(CPU_Engine, "_default_install_dir", return_value=install):
            with pytest.raises(EngineException, match="Quantizer binary not found"):
                CPU_Engine.quant_and_save_from_hf_format(src, dst)

    def test_legacy_quantize_binary_name_is_accepted(self, tmp_path, monkeypatch):
        src, dst, install = self._setup_safetensors_job(tmp_path, monkeypatch)
        quantizer_name = "llama-quantize.exe" if os.name == "nt" else "llama-quantize"
        legacy_name = "quantize.exe" if os.name == "nt" else "quantize"
        (install / quantizer_name).rename(install / legacy_name)
        with patch.object(CPU_Engine, "_default_install_dir", return_value=install):
            CPU_Engine.quant_and_save_from_hf_format(src, dst, quantize=True)
        assert (dst / "model-q4_k_m.gguf").exists()

    def test_converter_falls_back_to_cuda_artifact_dir(self, tmp_path, monkeypatch):
        src, dst, install = self._setup_safetensors_job(tmp_path, monkeypatch)
        # Remove the converter from the CPU install dir and provide it only
        # in the cuda fallback location under the patched ROOT_DIR.
        (install / "convert_hf_to_gguf.py").unlink()
        cuda_bin = tmp_path / "root" / "artifacts" / "llama-cpp" / "cuda" / "bin"
        _write_converter_script(cuda_bin)
        with patch.object(CPU_Engine, "_default_install_dir", return_value=install):
            CPU_Engine.quant_and_save_from_hf_format(src, dst, quantize=False)
        assert (dst / "model-f16.gguf").exists()

    def test_frozen_build_uses_inprocess_converter(self, tmp_path, monkeypatch):
        src, dst, install = self._setup_safetensors_job(tmp_path, monkeypatch)

        def fake_inprocess(converter, install_dir, src_path, fp16):
            Path(fp16).write_bytes(b"GGUF" + b"\x00" * 64)
            return 0

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        with patch.object(CPU_Engine, "_default_install_dir", return_value=install):
            with patch.object(
                CPU_Engine, "_run_converter_inprocess", side_effect=fake_inprocess
            ) as inproc:
                CPU_Engine.quant_and_save_from_hf_format(src, dst, quantize=False)
        inproc.assert_called_once()
        assert (dst / "model-f16.gguf").exists()


# =====================================================================
# UNIT - _run_converter_inprocess (real dynamic import)
# =====================================================================

@pytest.mark.unit
class TestRunConverterInprocess:

    def test_success_writes_outfile_and_restores_state(self, tmp_path):
        install = tmp_path / "install"
        converter = _write_converter_script(install, "ok")
        out = tmp_path / "model-f16.gguf"
        argv_before = sys.argv[:]

        rc = CPU_Engine._run_converter_inprocess(
            converter, install, tmp_path / "src", out
        )

        assert rc == 0
        assert out.exists()
        assert sys.argv == argv_before
        assert "convert_hf_to_gguf" not in sys.modules

    def test_nonzero_systemexit_propagates_code(self, tmp_path):
        install = tmp_path / "install"
        converter = _write_converter_script(install, "exit3")
        rc = CPU_Engine._run_converter_inprocess(
            converter, install, tmp_path / "src", tmp_path / "out.gguf"
        )
        assert rc == 3

    def test_exception_returns_one(self, tmp_path):
        install = tmp_path / "install"
        converter = _write_converter_script(install, "crash")
        rc = CPU_Engine._run_converter_inprocess(
            converter, install, tmp_path / "src", tmp_path / "out.gguf"
        )
        assert rc == 1
