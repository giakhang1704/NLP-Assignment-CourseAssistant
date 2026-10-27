"""Translate semantic frames into retrieval requests without executing them."""

_SOURCES = {"GET_COURSE_INFO": ["course_info.txt"],
            "GET_SCHEDULE": ["schedule.txt"], "GET_TOPIC": ["topics.txt", "fag.txt"],
            "GET_ASSIGNMENT": ["assignments.txt"], "GET_DEADLINE": ["assignments.txt", "schedule.txt"],
            "GET_RESOURCE": ["resources.txt"], "GET_RULE": ["regulations.txt"],
            "GET_LO": ["course_info.txt"], "GET_INSTRUCTOR": ["course_info.txt"]}


def build_query(frame, original_question):
    """Preserve the original question and express source preferences, not gates.

    A future retriever may boost preferred sources, but should still search
    other evidence. Unresolved references must be handled before retrieval.
    """
    hints = [frame.get("attribute"), frame.get("operation")]
    hints.extend(str(entity["value"]) for entity in frame.get("entities", [])
                 if entity.get("value") is not None and entity["type"] != "reference")
    text = original_question
    if any(hints):
        text += "\n" + " ".join(str(hint) for hint in hints if hint)
    return {"mode": "semantic", "text": text, "original_question": original_question,
            "intent": frame["intent"], "question_type": frame["question_type"],
            "attribute": frame.get("attribute"), "operation": frame.get("operation"),
            "entities": [dict(entity) for entity in frame.get("entities", [])],
            "filters": {}, "preferred_sources": list(_SOURCES.get(frame["intent"], [])),
            "needs_context": frame.get("needs_context", False)}


def build_fallback_query(original_question):
    """Hand off an unparsed question without inventing semantics or domain labels.

    Grammar coverage cannot determine answerability or domain membership.
    Context requirements are unknown until a later stage checks the raw question.
    This request does not execute retrieval or authorize an unsupported answer.
    """
    return {"mode": "raw_question", "text": original_question,
            "original_question": original_question, "intent": "UNKNOWN",
            "question_type": "unknown", "attribute": None, "operation": None,
            "entities": [], "filters": {}, "preferred_sources": [],
            "needs_context": None}
