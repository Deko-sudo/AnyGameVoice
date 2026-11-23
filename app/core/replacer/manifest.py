"""On-disk records for multi-file voice mods."""

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from tempfile import NamedTemporaryFile


def _atomic_write(path: Path, payload: str) -> None:
    stream = NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False)
    staged = Path(stream.name)
    try:
        with stream:
            stream.write(payload)
        staged.replace(path)
    except BaseException:
        staged.unlink(missing_ok=True)
        raise


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise ValueError(f"Invalid relative path: {value!r}")
    path = PurePosixPath(value)
    if not path.parts or path.is_absolute() or PureWindowsPath(value).drive or ".." in path.parts:
        raise ValueError(f"Invalid relative path: {value!r}")
    return path


@dataclass
class ManifestEntry:
    original: str
    backup: str
    replaced_with: str
    sha256_original: str
    sha256_replaced: str
    installed_at: str
    uninstalled_at: str | None = None
    status: str = "installed"


@dataclass
class ModManifest:
    install_id: str
    created_at: str
    game_root: str
    output_dir: str
    entries: list[ManifestEntry]

    def to_json(self) -> str:
        self.validate()
        return json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n"

    @classmethod
    def from_json(cls, path: str | Path) -> "ModManifest":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        try:
            data["entries"] = [ManifestEntry(**entry) for entry in data["entries"]]
            manifest = cls(**data)
        except (KeyError, TypeError) as exc:
            raise ValueError("Invalid manifest structure") from exc
        manifest.validate()
        return manifest

    def validate(self) -> None:
        if not isinstance(self.install_id, str) or not re.fullmatch(
            r"\d{8}T\d{6}\.\d{6}Z-[\da-f]{6}", self.install_id, flags=re.ASCII,
        ):
            raise ValueError("Invalid install_id")
        for root in (self.game_root, self.output_dir):
            if not isinstance(root, str) or "\0" in root or not Path(root).is_absolute():
                raise ValueError(f"Manifest directory must be absolute: {root!r}")
        originals, backups = set(), set()
        for entry in self.entries:
            original = _relative_path(entry.original)
            backup = _relative_path(entry.backup)
            _relative_path(entry.replaced_with)
            if original in originals or backup in backups:
                raise ValueError("Duplicate original or backup in manifest")
            originals.add(original)
            backups.add(backup)
            for digest in (entry.sha256_original, entry.sha256_replaced):
                if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
                    raise ValueError(f"Invalid SHA-256 for {entry.original}")
            if entry.status not in ("installed", "uninstalled", "conflict", "missing"):
                raise ValueError(f"Invalid status for {entry.original}: {entry.status!r}")
