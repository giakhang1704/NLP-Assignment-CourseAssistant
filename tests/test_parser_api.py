"""API status and source-mention contracts independent of QA answers."""
import json
import unicodedata
import unittest
from course_assistant.parsing.api import CourseParser


class ParserAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = CourseParser()

    def test_unrecognized_form_does_not_claim_outside_domain(self):
        result = self.parser.parse("Xin giải thích thêm thuật toán theo cách chưa có trong grammar nhé")
        self.assertFalse(result["is_valid"])
        self.assertEqual("unsupported_form", result["status"])
        self.assertEqual("not_in_grammar", result["error"])
        self.assertEqual("()", result["parse_tree"])
        self.assertIsNone(result["semantic_frame"])
        self.assertEqual("raw_question", result["query"]["mode"])
        self.assertEqual(result["sentence"], result["query"]["text"])

    def test_unparsed_questions_preserve_raw_text_without_domain_or_intent_guesses(self):
        for question in ["Inflection khác Derivation ở điểm nào vậy?",
                         "Xin giải thích vì sao Chart Parsing không phải tính lại mọi thứ",
                         "Thời tiết Đà Lạt ngày mai ra sao?",
                         unicodedata.normalize("NFD", "Cái phần vừa nói còn cách giải thích nào khác?")]:
            with self.subTest(question=question):
                result = self.parser.parse(question)
                self.assertEqual("unsupported_form", result["status"])
                self.assertFalse(result["is_valid"])
                self.assertEqual("()", result["parse_tree"])
                self.assertIsNone(result["semantic_frame"])
                query = result["query"]
                self.assertEqual("raw_question", query["mode"])
                self.assertEqual(question, query["text"])
                self.assertEqual(question, query["original_question"])
                self.assertEqual("UNKNOWN", query["intent"])
                self.assertIsNone(query["operation"])
                self.assertIsNone(query["attribute"])
                self.assertIsNone(query["needs_context"])
                self.assertEqual([], query["entities"])
                self.assertEqual([], query["preferred_sources"])
                self.assertEqual({}, query["filters"])

    def test_empty_and_overlength_are_separate_statuses(self):
        for sentence, status in [("  ", "empty_input"), ("a " * 129, "input_too_long")]:
            with self.subTest(status=status):
                result = self.parser.parse(sentence)
                self.assertEqual(status, result["status"])
                self.assertIsNone(result["query"])
                self.assertIsNone(result["semantic_frame"])

    def test_explicit_entity_surface_uses_original_case_and_offsets(self):
        question = "Cho tôi biết MÔN NLP có bao nhiêu tín chỉ?"
        result = self.parser.parse(question)
        mention = next(m for m in result["mentions"] if m["id"] == "CO3085")
        self.assertEqual("NLP", mention["surface"])
        self.assertEqual("NLP", question[mention["start"]:mention["end"]])

    def test_decomposed_unicode_keeps_original_character_offsets(self):
        question = unicodedata.normalize("NFD", "Tuần 3 học gì?")
        result = self.parser.parse(question)
        self.assertTrue(result["is_valid"])
        mention = next(m for m in result["mentions"] if m["id"] == "WEEK_03")
        self.assertEqual(unicodedata.normalize("NFD", "Tuần 3"), mention["surface"])
        self.assertEqual(mention["surface"], question[mention["start"]:mention["end"]])

    def test_context_recognition_is_not_resolution(self):
        for question in ["Phần này cần xuất file gì?", "Còn yêu cầu của nó thì sao?",
                         "Môn này có bao nhiêu tín chỉ?"]:
            with self.subTest(question=question):
                result = self.parser.parse(question)
                self.assertTrue(result["is_valid"])
                self.assertEqual("needs_context", result["status"])
                self.assertTrue(result["needs_context"])
                self.assertTrue(result["query"]["needs_context"])

    def test_analyze_is_json_serializable_and_matches_parse(self):
        question = "CFG là gì?"
        result = self.parser.analyze(question)
        self.assertEqual(self.parser.parse(question), result)
        self.assertIn("semantic_frame", json.loads(json.dumps(result)))

    def test_reject_invalid_max_tokens(self):
        for value in [0, -1, True, 1.5]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                CourseParser(max_tokens=value)


if __name__ == "__main__":
    unittest.main()
