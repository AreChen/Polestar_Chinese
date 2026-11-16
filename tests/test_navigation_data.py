"""Regression checks for navigation data distributed as Lua source files.

Run from the repository root with: python -m unittest discover -s tests
Set POLESTAR_NAV_ROOT to validate an extracted addon or another source tree.
"""

import os
from pathlib import Path
import re
import unittest
import zlib


ROOT = Path(os.environ.get("POLESTAR_NAV_ROOT", Path(__file__).resolve().parents[1]))
DATA_DIRS = ("Polestar_Nav/Nav", "Polestar_Nav_EK", "Polestar_Nav_Kalimdor")
NAME = re.compile(r"Nav\d+_\d+\.lua\Z")
START = re.compile(rb"^data\.packed\.", re.MULTILINE)
ASSIGNMENT = re.compile(rb"^data\.packed\.[A-Za-z]+\[\d+\]\s*=\s*\{([^\r\n]*)\}[ \t]*$", re.MULTILINE)
STRING = re.compile(rb'"((?:[^"\\\r\n]|\\[0-9]{3})*)"')
ESCAPE = re.compile(rb"\\([0-9]{3})")


def navigation_files():
    files = sorted(path for folder in DATA_DIRS for path in (ROOT / folder).glob("Nav*_*.lua") if NAME.fullmatch(path.name))
    if not files:
        raise AssertionError(f"No navigation files found under {ROOT}")
    return files


def decode_escape(match):
    value = int(match.group(1))
    if value > 255:
        raise ValueError("Lua decimal escape exceeds 255")
    return bytes([value])


class NavigationDataTest(unittest.TestCase):
    def test_sources_survive_utf8_replacement(self):
        for file in navigation_files():
            data = file.read_bytes()
            self.assertTrue(
                data.decode("utf-8", "replace").encode("utf-8") == data,
                f"{file.relative_to(ROOT)} changes when processed as UTF-8 text",
            )

    def test_all_packed_chunks_decompress(self):
        total_chunks = 0
        for file in navigation_files():
            data = file.read_bytes()
            assignments = list(ASSIGNMENT.finditer(data))
            with self.subTest(file=file.relative_to(ROOT)):
                self.assertGreater(len(assignments), 0)
                self.assertEqual(len(assignments), len(START.findall(data)), "unrecognized packed assignment")
                for assignment in assignments:
                    body = assignment.group(1)
                    strings = list(STRING.finditer(body))
                    self.assertGreater(len(strings), 0)
                    self.assertEqual(STRING.sub(b"", body).strip(b" ,\t"), b"", "unrecognized Lua expression")
                    for string in strings:
                        packed = ESCAPE.sub(decode_escape, string.group(1))
                        try:
                            zlib.decompress(packed)
                        except zlib.error as exc:
                            self.fail(f"{file.relative_to(ROOT)}: invalid compressed chunk: {exc}")
                        total_chunks += 1
        self.assertGreater(total_chunks, 0)


if __name__ == "__main__":
    unittest.main()
