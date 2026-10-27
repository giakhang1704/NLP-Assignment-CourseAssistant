"""Support grading mounts as well as the default project input/output paths."""
from pathlib import Path
from .cli import main


def run():
    grading_input = Path("/nlp/input/sentences.txt")
    args = (["run", "--input", str(grading_input), "--output-dir", "/nlp/output"]
            if grading_input.is_file() else ["run"])
    return main(args)


if __name__ == "__main__":
    raise SystemExit(run())
