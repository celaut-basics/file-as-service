"""Local checks for pack manifests. This does not pack or start a node."""
import json
import stat
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("film", "game", "pdf")
ARCH_ALIASES = {
    "linux/amd64",
    "amd64",
    "x86_64",
    "linux/arm64",
    "arm64",
    "arm_64",
    "aarch64",
}


class ManifestTests(unittest.TestCase):
    def test_service_json_matches_current_nodo(self):
        for kind in KINDS:
            path = ROOT / kind / ".service" / "service.json"
            with self.subTest(kind=kind):
                data = json.loads(path.read_text())
                self.assertNotIn("gas_amount_per_call", json.dumps(data))
                self.assertNotIn("entrypoint", data)
                self.assertEqual(data["tag"], f"file-as-service-{kind}")
                self.assertIn(data["architecture"], ARCH_ALIASES)
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
        for kind in KINDS:
            path = ROOT / kind / ".service" / "pack_config.json"
            with self.subTest(kind=kind):
                data = json.loads(path.read_text())
                self.assertEqual(data["include"], ["service"])
                self.assertFalse(data.get("zip", False))
                self.assertIn("__pycache__", data.get("ignore", []))

    def test_dockerfile_copy_sources_start_with_dot(self):
        for kind in KINDS:
            text = (ROOT / kind / ".service" / "Dockerfile").read_text()
            with self.subTest(kind=kind):
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


if __name__ == "__main__":
    unittest.main()
