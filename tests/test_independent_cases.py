from pathlib import Path
import unittest
from course_assistant.config import PROJECT_ROOT
from course_assistant.parsing.api import CourseParser
from course_assistant.evaluation.runner import evaluate_cases


class IndependentSemanticCases(unittest.TestCase):
    def test_semantic_slots_and_negatives(self):
        summary, rows = evaluate_cases(CourseParser(), PROJECT_ROOT / "data/evaluation/independent_cases.jsonl")
        for row in rows:
            with self.subTest(sentence=row["sentence"]):
                self.assertTrue(row["correct"], row)


if __name__ == "__main__":
    unittest.main()
