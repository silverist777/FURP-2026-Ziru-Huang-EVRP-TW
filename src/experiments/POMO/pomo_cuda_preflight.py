"""Preflight checks for CUDA-based POMO preparation.

This script is intentionally independent from the EVRP-TW PyVRP baseline.
It only checks whether the current Python environment can see NVIDIA CUDA
through PyTorch and can run a tiny GPU tensor operation.
"""

from __future__ import annotations

import argparse
import importlib
import json
import platform
import subprocess
import sys
from typing import Any


def run_command(command: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return {
            "found": False,
            "returncode": None,
            "stdout": "",
            "stderr": "command not found",
        }

    return {
        "found": True,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def import_version(module_name: str) -> str | None:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        return f"import failed: {exc.__class__.__name__}: {exc}"
    return getattr(module, "__version__", "version unknown")


def collect_report() -> dict[str, Any]:
    report: dict[str, Any] = {
        "python_executable": sys.executable,
        "python_version": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "nvidia_smi": run_command(["nvidia-smi"]),
        "nvcc": run_command(["nvcc", "--version"]),
        "packages": {
            "torch": import_version("torch"),
            "torchvision": import_version("torchvision"),
            "torchaudio": import_version("torchaudio"),
            "numpy": import_version("numpy"),
            "rl4co": import_version("rl4co"),
        },
    }

    try:
        torch = importlib.import_module("torch")
    except ImportError:
        report["torch_import_ok"] = False
        report["torch_error"] = "torch is not installed"
        return report

    report["torch_import_ok"] = True
    report["torch_cuda_version"] = getattr(torch.version, "cuda", None)
    report["torch_cuda_available"] = bool(torch.cuda.is_available())
    report["cuda_device_count"] = int(torch.cuda.device_count())

    if not torch.cuda.is_available():
        report["cuda_matmul_ok"] = False
        report["cuda_reason"] = "PyTorch cannot access CUDA from this environment."
        return report

    device = torch.device("cuda:0")
    report["cuda_device_name"] = torch.cuda.get_device_name(0)
    props = torch.cuda.get_device_properties(0)
    report["cuda_total_memory_mib"] = int(props.total_memory // (1024 * 1024))

    a = torch.randn((512, 512), device=device)
    b = torch.randn((512, 512), device=device)
    c = a @ b
    torch.cuda.synchronize()
    report["cuda_matmul_ok"] = bool(c.is_cuda and c.shape == (512, 512))
    return report


def print_human(report: dict[str, Any]) -> None:
    print("POMO CUDA preflight")
    print("====================")
    print(f"python_executable: {report['python_executable']}")
    print(f"python_version: {report['python_version']}")
    print(f"platform: {report['platform']}")

    nvidia = report["nvidia_smi"]
    print(f"nvidia_smi_found: {nvidia['found']}")
    if nvidia["found"]:
        first_line = nvidia["stdout"].splitlines()[0] if nvidia["stdout"] else ""
        print(f"nvidia_smi_first_line: {first_line}")

    nvcc = report["nvcc"]
    print(f"nvcc_found: {nvcc['found']}")
    print(f"packages: {report['packages']}")
    print(f"torch_import_ok: {report.get('torch_import_ok', False)}")
    print(f"torch_cuda_version: {report.get('torch_cuda_version')}")
    print(f"torch_cuda_available: {report.get('torch_cuda_available')}")
    print(f"cuda_device_count: {report.get('cuda_device_count')}")
    if report.get("cuda_device_name"):
        print(f"cuda_device_name: {report['cuda_device_name']}")
        print(f"cuda_total_memory_mib: {report['cuda_total_memory_mib']}")
    print(f"cuda_matmul_ok: {report.get('cuda_matmul_ok')}")
    if report.get("cuda_reason"):
        print(f"cuda_reason: {report['cuda_reason']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check CUDA readiness for POMO.")
    parser.add_argument("--json", action="store_true", help="Print raw JSON report.")
    args = parser.parse_args()

    report = collect_report()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human(report)


if __name__ == "__main__":
    main()
