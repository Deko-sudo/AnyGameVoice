"""Local hardware inventory. Modified 2026-10-22: memory headroom and AMD support."""

import os
import platform
from pathlib import Path
import shutil
import subprocess

DRM_ROOT = Path('/sys/class/drm')
GIB = 1024 ** 3


def _read_gib(path):
    try:
        return round(int(path.read_text().strip()) / GIB, 2)
    except (OSError, ValueError):
        return None


def _linux_gpus():
    found = []
    for card in sorted(DRM_ROOT.glob('card[0-9]*')):
        if not card.name[4:].isdigit():
            continue
        device = card / 'device'
        total = _read_gib(device / 'mem_info_vram_total')
        if total is None:
            continue
        used = _read_gib(device / 'mem_info_vram_used')
        try:
            vendor_id = (device / 'vendor').read_text().strip()
        except OSError:
            vendor_id = ''
        vendor = {'0x1002': 'AMD', '0x10de': 'NVIDIA', '0x8086': 'Intel'}.get(vendor_id, 'GPU')
        found.append({'name': f'{vendor} · {card.name}', 'vendor': vendor, 'vram_gb': total,
                      'free_vram_gb': round(max(0, total - used), 2) if used is not None else None,
                      'source': 'linux-drm', 'accelerator_verified': False})
    # PCI labels improve the display; they never prove framework/driver compatibility.
    if found and shutil.which('lspci'):
        try:
            text = subprocess.run(['lspci', '-mm'], capture_output=True, text=True, timeout=2, check=True).stdout
            labels = [line for line in text.splitlines() if any(x in line for x in ('VGA compatible', '3D controller', 'Display controller'))]
            for gpu in found:
                device = (DRM_ROOT / gpu['name'].split(' · ')[-1] / 'device').resolve().name
                match = next((line for line in labels if line.startswith(device.removeprefix('0000:') + ' ')), '')
                if match:
                    parts = match.split('"')
                    if len(parts) >= 6:
                        gpu['name'] = parts[5]
        except (OSError, subprocess.SubprocessError):
            pass
    return found


def scan_hardware() -> dict:
    info = {'os': f'{platform.system()} {platform.release()}', 'cpu_count': os.cpu_count() or 1,
            'ram_gb': 0.0, 'available_ram_gb': None, 'free_disk_gb': None,
            'gpu': 'unknown', 'vram_gb': 0.0, 'free_vram_gb': None, 'gpus': []}
    try:
        import psutil
        memory = psutil.virtual_memory()
        info.update(ram_gb=round(memory.total / GIB, 1), available_ram_gb=round(memory.available / GIB, 1))
        info['free_disk_gb'] = round(shutil.disk_usage(os.path.expanduser('~')).free / GIB, 1)
    except Exception as exc:
        info['error'] = f'psutil: {type(exc).__name__}'
    try:
        import GPUtil
        info['gpus'] = [{'name': gpu.name, 'vendor': 'NVIDIA', 'vram_gb': round(gpu.memoryTotal / 1024, 2),
                         'free_vram_gb': round(gpu.memoryFree / 1024, 2), 'source': 'nvidia-smi',
                         'accelerator_verified': False} for gpu in GPUtil.getGPUs()]
    except Exception:
        pass
    if platform.system() == 'Linux':
        linux_gpus = _linux_gpus()
        info['gpus'].extend(gpu for gpu in linux_gpus if gpu['vendor'] != 'NVIDIA' or not any(item['vendor'] == 'NVIDIA' for item in info['gpus']))
    if info['gpus']:
        best = max(info['gpus'], key=lambda gpu: gpu['vram_gb'])
        info.update(gpu=best['name'], vram_gb=best['vram_gb'], free_vram_gb=best['free_vram_gb'])
    return info


def recommend_settings(hardware: dict) -> dict:
    """Conservative default; never select an unverified GPU backend by VRAM alone."""
    ram = float(hardware.get('ram_gb', 0) or 0)
    vram = float(hardware.get('vram_gb', 0) or 0)
    tier = 'ideal' if vram >= 12 else 'recommended' if vram >= 6 or ram >= 16 else 'minimum'
    return {'tier': tier, 'batch_size': 1, 'engine': 'piper'}


__all__ = ['scan_hardware', 'recommend_settings']
