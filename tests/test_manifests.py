"""Local checks for pack manifests. This does not pack or start a node."""
import json
import os
import stat
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("film", "game", "pdf")
ARCHES = ("amd64", "arm64")


def pack_roots():
    """(kind, arch, pack root) for each capsule and architecture."""
    for kind in KINDS:
        for arch in ARCHES:
            yield kind, arch, ROOT / kind / arch


class ManifestTests(unittest.TestCase):
    def test_service_json_matches_current_nodo(self):
        for kind, arch, root in pack_roots():
            path = root / ".service" / "service.json"
            with self.subTest(kind=kind, arch=arch):
                data = json.loads(path.read_text())
                self.assertNotIn("gas_amount_per_call", json.dumps(data))
                self.assertNotIn("entrypoint", data)
                self.assertEqual(data["tag"], f"file-as-service-{kind}")
                self.assertEqual(data["architecture"], f"linux/{arch}")
                self.assertIs(data["read_only_filesystem"], True)
                self.assertNotIn("shared_filesystems", data)
                self.assertEqual(data["init"]["entry_path"], "/service/entrypoint.sh")
                self.assertEqual(data["network"], [])
                api = data["api"]
                self.assertEqual(len(api), 1)
                self.assertEqual(api[0]["port"], 8080)
                self.assertEqual(api[0]["transport"], "tcp")
                self.assertEqual(
                    api[0]["protocol"], ["http", f"file-as-service-{kind}"]
                )
                at_init = data["resources"]["at_init"]
                at_most = data["resources"]["at_most"]
                self.assertGreaterEqual(at_most["mem_limit"], at_init["mem_limit"])
                self.assertGreaterEqual(at_most["disk_space"], at_init["disk_space"])
                # Ceiling for a read-only tree (~135-215 MiB on 2026-09-16).
                self.assertEqual(at_init["disk_space"], 536870912)
                self.assertEqual(at_most["disk_space"], 536870912)

    def test_pack_config_include_service(self):
        for kind, arch, root in pack_roots():
            path = root / ".service" / "pack_config.json"
            with self.subTest(kind=kind, arch=arch):
                data = json.loads(path.read_text())
                self.assertEqual(data["include"], ["service"])
                self.assertFalse(data.get("zip", False))
                self.assertIn("__pycache__", data.get("ignore", []))

    def test_dockerfile_copy_sources_start_with_dot(self):
        for kind, arch, root in pack_roots():
            text = (root / ".service" / "Dockerfile").read_text()
            with self.subTest(kind=kind, arch=arch):
                self.assertTrue(text.startswith("FROM "))
                for line in text.splitlines():
                    stripped = line.strip()
                    if not stripped.startswith("COPY "):
                        continue
                    if "--from=" in stripped:
                        continue
                    parts = stripped.split()
                    sources = [p for p in parts[1:-1] if not p.startswith("--")]
                    self.assertTrue(sources, stripped)
                    for source in sources:
                        self.assertTrue(
                            source.startswith("./"),
                            f"{kind} COPY source {source!r} must start with ./",
                        )

    def test_entrypoint_is_posix_shell(self):
        for kind in KINDS:
            path = ROOT / kind / "service" / "entrypoint.sh"
            with self.subTest(kind=kind):
                data = path.read_bytes()
                self.assertFalse(b"\r" in data, "CRLF line endings")
                text = data.decode()
                self.assertTrue(text.startswith("#!/bin/sh\n"))
                self.assertIn("exec python3 /service/app.py", text)
                self.assertIn("PYTHONDONTWRITEBYTECODE=1", text)
                mode = path.stat().st_mode
                self.assertTrue(mode & stat.S_IXUSR)

    def test_payload_is_present_and_not_routed(self):
        self.assertTrue((ROOT / "film/service/payload.mp4").is_file())
        self.assertTrue((ROOT / "game/service/payload.ch8").is_file())
        self.assertTrue((ROOT / "pdf/service/payload.pdf").is_file())
        for kind in KINDS:
            app = (ROOT / kind / "service" / "app.py").read_text()
            http = (ROOT / "common/http_base.py").read_text()
            with self.subTest(kind=kind):
                self.assertNotIn("/payload", http)
                self.assertNotIn("sendfile", app.lower())
                self.assertIn("0.0.0.0", http)

    def test_prepare_emits_current_manifest(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "prepare", ROOT / "tools" / "prepare.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        data = module.manifest("film", "amd64")
        self.assertEqual(data["architecture"], "linux/amd64")
        self.assertIs(data["read_only_filesystem"], True)
        for kind, arch, root in pack_roots():
            with self.subTest(kind=kind, arch=arch):
                written = json.loads((root / ".service" / "service.json").read_text())
                self.assertEqual(written, module.manifest(kind, arch))


class PerArchitectureLayoutTests(unittest.TestCase):
    """One pack root per architecture, as celaut-basics/demo-service has.

    `nodo pack <kind>/<arch>` reads only `<kind>/<arch>/.service/` and copies
    the root with its symlinks followed. So the root holds real `.service/`
    files and reaches the shared source through `service -> ../service`.
    """

    def test_no_service_dir_at_the_old_place(self):
        for kind in KINDS:
            self.assertFalse((ROOT / kind / ".service").exists(), kind)

    def test_each_pack_root_has_real_service_files(self):
        for kind, arch, root in pack_roots():
            for name in ("Dockerfile", "service.json", "pack_config.json"):
                path = root / ".service" / name
                with self.subTest(kind=kind, arch=arch, name=name):
                    self.assertTrue(path.is_file())
                    self.assertFalse(path.is_symlink())

    def test_shared_source_is_a_link_in_each_pack_root(self):
        for kind, arch, root in pack_roots():
            link = root / "service"
            with self.subTest(kind=kind, arch=arch):
                self.assertTrue(link.is_symlink())
                self.assertEqual(os.readlink(link), "../service")
                self.assertTrue((link / "entrypoint.sh").is_file())

    def test_both_architectures_differ_only_in_architecture(self):
        for kind in KINDS:
            specs = {}
            for arch in ARCHES:
                spec = json.loads((ROOT / kind / arch / ".service" / "service.json").read_text())
                spec.pop("architecture")
                specs[arch] = spec
            dockerfiles = {
                arch: (ROOT / kind / arch / ".service" / "Dockerfile").read_text()
                for arch in ARCHES
            }
            configs = {
                arch: (ROOT / kind / arch / ".service" / "pack_config.json").read_text()
                for arch in ARCHES
            }
            with self.subTest(kind=kind):
                self.assertEqual(specs["amd64"], specs["arm64"])
                self.assertEqual(dockerfiles["amd64"], dockerfiles["arm64"])
                self.assertEqual(configs["amd64"], configs["arm64"])


if __name__ == "__main__":
    unittest.main()
