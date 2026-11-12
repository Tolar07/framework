"""Vendored files must equal olp-common's (Tolar07/olp-common, tools/vendor.py).

If this fails you edited a shared file inside this bot. Make the change in olp-common instead, then
run `python tools/vendor.py <this repo>` there and commit both.
"""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def lf_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


class VendoredTest(unittest.TestCase):
    def test_vendored_files_match_manifest(self):
        man = json.loads((ROOT / "VENDORED.json").read_text(encoding="utf-8"))
        self.assertTrue(man["files"])
        for dest, want in man["files"].items():
            with self.subTest(dest=dest):
                self.assertEqual(lf_sha(ROOT / dest), want, f"{dest} drifted from olp-common")


if __name__ == "__main__":
    unittest.main()
