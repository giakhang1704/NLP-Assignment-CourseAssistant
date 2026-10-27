"""Behavioral checks for the parser-to-retrieval handoff."""
import unittest
from course_assistant.parsing.api import CourseParser
from course_assistant.semantics.query_builder import build_query


class SemanticFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = CourseParser()

    def test_requested_course_attributes_are_distinct(self):
        credits = self.parser.parse("Môn NLP có bao nhiêu tín chỉ?")["semantic_frame"]
        department = self.parser.parse("Môn NLP thuộc khoa nào?")["semantic_frame"]
        self.assertEqual("GET_COURSE_INFO", credits["intent"])
        self.assertEqual("credits", credits["attribute"])
        self.assertEqual("department", department["attribute"])
        self.assertNotEqual(credits, department)

    def test_course_chapter_count_variants(self):
        for sentence in ["NLP có mấy chương?", "Môn NLP có bao nhiêu chương?",
                         "CO3085 gồm mấy chương?", "Môn học có tổng cộng bao nhiêu chương?"]:
            with self.subTest(sentence=sentence):
                result = self.parser.parse(sentence)
                self.assertTrue(result["is_valid"])
                self.assertFalse(result["ambiguity"])
                self.assertEqual("GET_COURSE_INFO", result["semantic_frame"]["intent"])
                self.assertEqual("chapter_count", result["semantic_frame"]["attribute"])
                self.assertEqual("chapter_count", result["query"]["attribute"])
                self.assertIn("CO3085", {e["id"] for e in result["entities"]})
        self.assertFalse(self.parser.parse("Môn toán có mấy chương?")["is_valid"])

    def test_definition_and_process_keep_legacy_and_normalized_intents(self):
        for sentence, legacy, kind in [("CFG là gì?", "DEFINITION_QUERY", "definition"),
                                       ("Top-down parser hoạt động như thế nào?", "PROCESS_QUERY", "process")]:
            with self.subTest(sentence=sentence):
                result = self.parser.parse(sentence)
                self.assertEqual(legacy, result["intent_type"])
                self.assertEqual("GET_TOPIC", result["semantic_frame"]["intent"])
                self.assertEqual(kind, result["semantic_frame"]["question_type"])

    def test_comparison_preserves_order_and_repeated_arguments(self):
        result = self.parser.parse("So sánh PCFG và CFG")
        arguments = result["semantic_frame"]["arguments"]
        self.assertEqual([("left", "PCFG"), ("right", "CFG")],
                         [(argument["role"], argument["id"]) for argument in arguments])
        repeated = self.parser.parse("So sánh CFG và CFG")["semantic_frame"]["arguments"]
        self.assertEqual(2, len(repeated))
        self.assertEqual(["CFG", "CFG"], [argument["id"] for argument in repeated])

    def test_query_preserves_question_and_does_not_hard_gate_sources(self):
        question = "Môn NLP có bao nhiêu tín chỉ?"
        result = self.parser.parse(question)
        query = result["query"]
        self.assertEqual("semantic", query["mode"])
        self.assertEqual(question, query["original_question"])
        self.assertTrue(query["text"].startswith(question))
        self.assertIn("course_info.txt", query["preferred_sources"])
        self.assertEqual({}, query["filters"])

    def test_query_marks_unresolved_reference(self):
        result = self.parser.parse("Tài liệu của phần này ở đâu?")
        self.assertTrue(result["semantic_frame"]["needs_context"])
        self.assertTrue(result["query"]["needs_context"])
        self.assertTrue(result["semantic_frame"]["references"])
        self.assertFalse(any(entity["id"].startswith("CH") for entity in result["entities"]))

    def test_comparison_reference_keeps_right_operand_role(self):
        result = self.parser.parse("So sánh mô hình đó với CRF xem phương pháp nào tối ưu hơn?")
        frame = result["semantic_frame"]
        self.assertIsNotNone(frame)
        self.assertTrue(frame["needs_context"])
        self.assertEqual("reference", frame["arguments"][0]["type"])
        self.assertEqual("left", frame["arguments"][0]["role"])
        self.assertEqual("CRF", frame["arguments"][1]["id"])
        self.assertEqual("right", frame["arguments"][1]["role"])


if __name__ == "__main__":
    unittest.main()
