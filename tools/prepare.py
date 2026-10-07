"""Stage shared code and write pack manifests.

Each capsule has one pack root per architecture: <kind>/amd64 and
<kind>/arm64. Each root holds its own .service/ and a symlink
`service -> ../service` to the shared source. This writes the manifests
of both roots and makes the links. It does not write the Dockerfile.
"""
import argparse
import json
from pathlib import Path
import os
import shutil

ROOT = Path(__file__).resolve().parents[1]
ARCHES = ("amd64", "arm64")
ENTRYPOINT = """#!/bin/sh
export PATH=/usr/local/bin:/usr/bin:/bin
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
cd /service || exit 1
exec python3 /service/app.py
"""
# 512 MiB. For read_only_filesystem this is a ceiling, not a floor
# (nodo src/virtualizers/microvm/limits.py:416-441, 444-460).
DISK_CEILING = 536870912


def manifest(kind: str, arch: str) -> dict:
    return {
        "tag": "file-as-service-" + kind,
        "architecture": "linux/" + arch,
        "read_only_filesystem": True,
        "init": {"entry_path": "/service/entrypoint.sh"},
        "api": [
            {
                "port": 8080,
                "transport": "tcp",
                "protocol": ["http", "file-as-service-" + kind],
            }
        ],
        "network": [],
        "resources": {
            "at_init": {
                "mem_limit": 268435456,
                "disk_space": DISK_CEILING,
                "cpu_period": 100000,
                "cpu_quota": 200000,
            },
            "at_most": {
                "mem_limit": 536870912,
                "disk_space": DISK_CEILING,
                "cpu_period": 100000,
                "cpu_quota": 400000,
            },
        },
    }


def pack_config() -> dict:
    return {
        "service_dependencies_directory": "__services__",
        "metadata_dependencies_directory": "__metadata__",
        "blocks_directory": "__block__",
        "zip": False,
        "include": ["service"],
        "ignore": ["__pycache__"],
    }


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    for kind in ("film", "game", "pdf"):
        service = ROOT / kind / "service"
        shutil.copyfile(ROOT / "common/http_base.py", service / "http_base.py")
        script = service / "entrypoint.sh"
        script.write_text(ENTRYPOINT)
        script.chmod(0o755)
        for arch in ARCHES:
            pack_root = ROOT / kind / arch
            service_dir = pack_root / ".service"
            service_dir.mkdir(parents=True, exist_ok=True)
            (service_dir / "service.json").write_text(
                json.dumps(manifest(kind, arch), indent=2) + "\n"
            )
            (service_dir / "pack_config.json").write_text(
                json.dumps(pack_config(), indent=2) + "\n"
            )
            link = pack_root / "service"
            if not link.is_symlink():
                os.symlink("../service", link)


if __name__ == "__main__":
    main()
