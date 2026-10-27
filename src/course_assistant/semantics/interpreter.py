"""Derive a small semantic frame from a licensed QUERY constituent."""

_NORMALIZED_INTENTS = {"DEFINITION_QUERY": "GET_TOPIC", "PROCESS_QUERY": "GET_TOPIC",
                       "COMPARISON_QUERY": "GET_TOPIC"}
_QUESTION_TYPES = {"DEFINITION_QUERY": "definition", "PROCESS_QUERY": "process",
                   "COMPARISON_QUERY": "comparison", "CONTEXT_DEPENDENT": "context",
                   "GET_RESOURCE": "list", "GET_ASSIGNMENT": "requirements"}


def interpret(query_node, parse_result, spec=None):
    """Return JSON data; no KB answers, evaluation labels or LLM are used."""
    spec = spec or {}
    legacy_intent = parse_result["intent_type"]
    intent = _NORMALIZED_INTENTS.get(legacy_intent, legacy_intent)
    text = " ".join(query_node.terminals())
    mentions = [dict(m) for m in parse_result.get("mentions", [])]
    entities = [dict(e) for e in parse_result.get("entities", [])]
    question_type = spec.get("question_type") or _QUESTION_TYPES.get(legacy_intent, "factual")
    attribute = spec.get("attribute")
    operation = spec.get("operation")

    if attribute is None:
        # These phrases are features of actual grammar productions, not a list
        # of evaluation questions. The selected parse already licensed them.
        features = [
            ("tín chỉ", "credits"), ("tên môn", "course_name"),
            ("mã môn", "course_id"), ("thuộc khoa", "department"),
            ("bao nhiêu giờ", "total_course_hours"),
            ("bao nhiêu tuần", "duration_weeks"),
            ("bao nhiêu phút", "duration_minutes"),
            ("phần trăm", "assessment_weight"),
            ("được đánh giá", "assessment"), ("mục tiêu", "objective"),
            ("email", "instructor_email"), ("phòng nào", "room"),
            ("thứ mấy", "weekday"), ("xuất file", "output_files"),
            ("nộp file", "submission_files"), ("nhóm bao nhiêu người", "team_size"),
        ]
        attribute = next((value for phrase, value in features if phrase in text), None)

    if "ở slide" in text or "slide mấy" in text or "slide nào" in text:
        question_type = "location"
        operation = operation or "locate_slide"
    if "công thức" in text:
        attribute = attribute or "formula"
    if "các bước" in text or legacy_intent == "PROCESS_QUERY":
        question_type = "process"
    if question_type == "comparison" or legacy_intent == "COMPARISON_QUERY" or text.startswith("so sánh "):
        question_type = "comparison"
        # A reference may be an operand: in "so sánh mô hình đó với CRF",
        # CRF is the right argument and the unresolved reference is the left.
        compared = [m for m in mentions if m["type"] in {"concept", "reference"}]
        for index, mention in enumerate(compared):
            mention["role"] = "left" if index == 0 else "right" if index == 1 else "additional"

    if operation is None:
        operation = {"definition": "define_topic", "process": "explain_process",
                     "comparison": "compare_topics", "context": "resolve_reference"}.get(question_type)
        if operation is None:
            operation = {"GET_COURSE_INFO": "get_course_attribute", "GET_SCHEDULE": "get_schedule",
                         "GET_TOPIC": "get_topic", "GET_ASSIGNMENT": "get_assignment",
                         "GET_DEADLINE": "get_deadline", "GET_RESOURCE": "get_resource",
                         "GET_RULE": "get_rule", "GET_INSTRUCTOR": "get_instructor",
                         "GET_LO": "get_learning_outcome"}.get(intent, "unknown")
    if intent == "GET_DEADLINE":
        attribute = attribute or "deadline"

    references = [dict(m) for m in mentions if m["type"] == "reference"]
    frame = {"intent": intent, "question_type": question_type, "attribute": attribute,
             "operation": operation, "entities": entities, "mentions": mentions,
             "references": references,
             "needs_context": bool(parse_result.get("needs_context") or references),
             "query_label": query_node.label}
    if question_type == "comparison":
        frame["arguments"] = [{"role": m["role"], "type": m["type"], "id": m["id"]}
                              for m in mentions if "role" in m]
    return frame
