"""Exercise the navigation conversion command with a real zlib stream."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "escape_nav_sources.py"
SOURCE = b'data.packed.graph[1] = {"x\x9c\xcbH\xcd\xc9\xc9\x07\\000\x06,\x02\x15"}\n'
EXPECTED = b'data.packed.graph[1] = {"x\\156\\203H\\205\\201\\201\x07\\000\x06,\x02\x15"}\n'


class ConversionTest(unittest.TestCase):
    def run_tool(self, *arguments):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, arguments)], capture_output=True, text=True)

    def test_converts_clean_data_and_can_check_the_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            nav = source / "Polestar_Nav_EK" / "Nav0_1.lua"
            nav.parent.mkdir(parents=True)
            nav.write_bytes(SOURCE)
            output = Path(tmp) / "output"
            result = self.run_tool(source, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((output / "Polestar_Nav_EK" / "Nav0_1.lua").read_bytes(), EXPECTED)
            self.assertEqual(nav.read_bytes(), SOURCE, "input must not be modified")
            checked = self.run_tool(output, "--check")
            self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_refuses_data_already_damaged_by_utf8_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            nav = source / "Polestar_Nav_EK" / "Nav0_1.lua"
            nav.parent.mkdir(parents=True)
            nav.write_bytes(SOURCE.decode("utf-8", "replace").encode("utf-8"))
            output = Path(tmp) / "output"
            result = self.run_tool(source, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((output / "Polestar_Nav_EK" / "Nav0_1.lua").exists())
            self.assertIn("ERROR", result.stderr)


if __name__ == "__main__":
    unittest.main()
