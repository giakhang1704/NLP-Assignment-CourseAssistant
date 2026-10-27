"""File contract and checkout execution regression tests."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from course_assistant.config import PROJECT_ROOT, DEFAULT_GRAMMAR_PATH
from course_assistant.exporters import read_sentences


class CheckoutContractTests(unittest.TestCase):
    def command(self, *args, cwd=None):
        return subprocess.run([sys.executable, "-B", "-X", "utf8", str(PROJECT_ROOT / "run.py"), *args],
                              capture_output=True, text=True, encoding="utf-8", cwd=cwd, timeout=40)

    def test_other_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.command("inspect", "Môn NLP có bao nhiêu tín chỉ?", cwd=directory)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(json.loads(result.stdout)["is_valid"])
            self.assertTrue(DEFAULT_GRAMMAR_PATH.is_file())

    def test_bad_limit_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "samples.txt"
            destination.write_text("KEEP", encoding="utf-8")
            result = self.command("generate", "--limit", "10001", "--output", str(destination))
            self.assertNotEqual(0, result.returncode)
            self.assertEqual("KEEP", destination.read_text(encoding="utf-8"))

    def test_bom_empty_lines_and_unknown_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.txt"
            destination = Path(directory) / "trees.txt"
            source.write_text("\ufeffCFG là gì?\n\nCFG là gì? 🙂\n", encoding="utf-8")
            result = self.command("parse", "--input", str(source), "--output", str(destination))
            self.assertEqual(0, result.returncode, result.stderr)
            trees = destination.read_text(encoding="utf-8").splitlines()
            self.assertEqual(3, len(trees))
            self.assertTrue(trees[0].startswith("(S "))
            self.assertEqual(["()", "()"], trees[1:])
            self.assertEqual(3, len(read_sentences(source)))


if __name__ == "__main__":
    unittest.main()
