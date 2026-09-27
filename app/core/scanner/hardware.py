"""Hardware scanner.

Collects local hardware info to recommend TTS settings.
Everything stays on device; caller decides whether to persist it.
"""

import os
import platform
import shutil


def _safe_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def scan_hardware() -> dict:
    """Return basic hardware info.

    Keys: os, cpu_count, ram_gb, free_disk_gb, gpu, vram_gb.
    Never raises: on error returns what was collected plus "error".
    """
    info: dict = {
        "os": f"{platform.system()} {platform.release()}",
        "cpu_count": os.cpu_count() or 1,
        "ram_gb": 0.0,
        "free_disk_gb": 0.0,
        "gpu": "unknown",
        "vram_gb": 0.0,
    }
    try:
        import psutil

        info["ram_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)
        info["free_disk_gb"] = round(
            shutil.disk_usage(os.path.expanduser("~")).free / (1024**3), 1
        )
    except Exception as exc:  # psutil missing or restricted
        info["error"] = f"psutil: {exc}"

    try:
        import GPUtil

        gpus = GPUtil.getGPUs()
        if gpus:
            gpu = gpus[0]
            info["gpu"] = gpu.name
            info["vram_gb"] = round(float(gpu.memoryTotal) / 1024, 1)
    except Exception:
        pass  # GPU info is best-effort

    return info


def recommend_settings(hardware: dict) -> dict:
    """Recommend TTS batch settings based on scanned hardware."""
    ram = float(hardware.get("ram_gb", 0) or 0)
    vram = float(hardware.get("vram_gb", 0) or 0)
    if vram >= 12:
        tier = "ideal"
    elif vram >= 6 or ram >= 16:
        tier = "recommended"
    else:
        tier = "minimum"
    batch = {"minimum": 1, "recommended": 4, "ideal": 8}[tier]
    engine = "xtts" if vram >= 6 else "piper"
    return {"tier": tier, "batch_size": batch, "engine": engine}


__all__ = ["scan_hardware", "recommend_settings"]
