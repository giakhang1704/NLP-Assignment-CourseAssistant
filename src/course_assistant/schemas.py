"""Shared handoff types. Runtime values remain JSON-serializable dictionaries."""
from typing import Any, TypedDict


class Entity(TypedDict, total=False):
    id: str
    type: str
    value: Any
    surface: str | None
    implicit: bool


class Mention(Entity, total=False):
    start: int | None
    end: int | None
    role: str


class SemanticFrame(TypedDict, total=False):
    intent: str
    question_type: str
    attribute: str | None
    operation: str | None
    entities: list[Entity]
    mentions: list[Mention]
    references: list[Entity]
    needs_context: bool
    query_label: str
    arguments: list[dict]


class RetrievalQuery(TypedDict, total=False):
    mode: str
    text: str
    original_question: str
    intent: str
    question_type: str
    attribute: str | None
    operation: str | None
    entities: list[Entity]
    filters: dict
    preferred_sources: list[str]
    needs_context: bool | None


class ParseResult(TypedDict, total=False):
    sentence: str
    normalized_sentence: str
    is_valid: bool
    status: str
    parse_tree: str
    intent_type: str
    entities: list[Entity]
    mentions: list[Mention]
    needs_context: bool
    ambiguity: bool
    candidate_intents: list[str]
    error: str | None
    semantic_frame: SemanticFrame | None
    query: RetrievalQuery | None
