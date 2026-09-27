"""Unreal support (unpacking included, with limits).

- detection (see detector.py markers: *.uproject, *.pak, *.utoc)
- audio asset inventory for the replacer
- .pak inspection: footer magic + version sniff (no AES key needed)
- unpacking: via UnrealPak CLI if present (common Engine paths + PATH),
  otherwise a clear error telling what to install.

Index parsing of encrypted paks needs the per-game AES key which we
don't have — that path raises a clear error instead of garbage.
"""

import os
import shutil
import struct
import subprocess
from pathlib import Path

from app.utils.audio_utils import carve_embedded_audio

__all__ = [
    "list_audio_assets",
    "extract_unreal_folder",
    "inspect_pak",
    "find_unrealpak",
    "unpack_pak",
    "extract_unreal_audio",
]

PAK_MAGIC = 0x5A6FA11E
CONTAINER_SUFFIXES = {".pak", ".utoc", ".ucas", ".uasset", ".ubulk"}
AUDIO_SUFFIXES = {".wav", ".ogg"}

# Common UnrealPak locations (UE 4.x/5.x). PATH is checked too.
UNREALPAK_CANDIDATES = [
    r"C:\Program Files\Epic Games\UE_5.4\Engine\Binaries\Win64\UnrealPak.exe",
    r"C:\Program Files\Epic Games\UE_5.3\Engine\Binaries\Win64\UnrealPak.exe",
    r"C:\Program Files\Epic Games\UE_5.2\Engine\Binaries\Win64\UnrealPak.exe",
    r"C:\Program Files\Epic Games\UE_4.27\Engine\Binaries\Win64\UnrealPak.exe",
]


def list_audio_assets(game_path: str, limit: int = 200) -> list[str]:
    """List loose audio files + pak/utoc containers."""
    found: list[str] = []
    for fp in Path(game_path).rglob("*"):
        if len(found) >= limit:
            break
        if fp.is_file() and fp.suffix.lower() in AUDIO_SUFFIXES | CONTAINER_SUFFIXES:
            found.append(os.path.relpath(fp, game_path))
    return sorted(found)


def extract_unreal_folder(game_path: str) -> list:
    """Unreal dialogue extraction: not implemented (needs unpacked assets)."""
    return []


def inspect_pak(path: str) -> dict:
    """Sniff a .pak footer: magic + version. No key needed.

    Returns {"path", "size", "is_pak", "version", "footer_offset"}.
    Raises FileNotFoundError for missing files.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Not found: {path}")
    size = os.path.getsize(path)
    info: dict = {"path": path, "size": size, "is_pak": False, "version": 0, "footer_offset": -1}
    if size < 8:
        return info
    with open(path, "rb") as fh:
        tail = fh.read(min(size, 4096))
    magic = struct.pack("<I", PAK_MAGIC)
    off = tail.rfind(magic)
    if off == -1:
        return info
    info["is_pak"] = True
    info["footer_offset"] = size - len(tail) + off
    if off + 8 <= len(tail):
        (ver,) = struct.unpack_from("<i", tail, off + 4)
        if 1 <= ver <= 20:
            info["version"] = ver
    return info


def find_unrealpak(exe: str = "") -> str:
    """Locate UnrealPak.exe (explicit path, PATH, common installs)."""
    if exe and os.path.isfile(exe):
        return exe
    found = shutil.which("UnrealPak") or shutil.which("UnrealPak.exe")
    if found:
        return found
    for cand in UNREALPAK_CANDIDATES:
        if os.path.isfile(cand):
            return cand
    return ""


def unpack_pak(pak_path: str, out_dir: str, unrealpak: str = "", aes_key: str = "") -> dict:
    """Unpack a .pak with UnrealPak CLI.

    Returns {"tool": path, "out_dir": out_dir, "returncode": int}.
    Raises RuntimeError when UnrealPak is missing (with inspect hints).
    """
    tool = find_unrealpak(unrealpak)
    if not tool:
        info = inspect_pak(pak_path)
        raise RuntimeError(
            "UnrealPak.exe not found. Install Unreal Engine or point "
            f"--unrealpak at it. Pak info: version={info['version']}, "
            f"size={info['size']} bytes. Encrypted paks additionally need "
            "the game's AES key (-cryptokeys=...)."
        )
    os.makedirs(out_dir, exist_ok=True)
    cmd = [tool, os.path.abspath(pak_path), "-Extract", os.path.abspath(out_dir)]
    if aes_key:
        cmd.append(f"-cryptokeys={aes_key}")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return {"tool": tool, "out_dir": out_dir, "returncode": proc.returncode, "log": proc.stdout[-2000:]}


def extract_unreal_audio(game_path: str, out_dir: str, unrealpak: str = "", aes_key: str = "") -> dict:
    """Extract audio from Unreal containers.

    Strategy per file: UnrealPak CLI when available; otherwise carve
    raw audio blobs from .ubulk loose files. Returns
    {"unpacked": [...], "carved": [...], "skipped": [...]}.
    """
    os.makedirs(out_dir, exist_ok=True)
    result: dict = {"unpacked": [], "carved": [], "skipped": []}
    tool = find_unrealpak(unrealpak)
    for fp in Path(game_path).rglob("*"):
        if not fp.is_file() or fp.suffix.lower() not in CONTAINER_SUFFIXES:
            continue
        dest = os.path.join(out_dir, fp.stem)
        if tool and fp.suffix.lower() == ".pak":
            try:
                r = unpack_pak(str(fp), dest, unrealpak=tool, aes_key=aes_key)
                if r["returncode"] == 0:
                    result["unpacked"].append(dest)
                    continue
            except RuntimeError:
                pass
            result["skipped"].append(str(fp))
        elif fp.suffix.lower() == ".ubulk":
            try:
                with open(fp, "rb") as fh:
                    data = fh.read()
                carved = carve_embedded_audio(data, dest, prefix=fp.stem)
                if carved:
                    result["carved"].extend(carved)
                else:
                    result["skipped"].append(str(fp))
            except OSError:
                result["skipped"].append(str(fp))
        else:
            result["skipped"].append(str(fp))
    return result
