"""Strict Vietnamese normalization; never discard unknown input characters."""
import re
import unicodedata

_TOKEN = re.compile(r"l\.o\.\d+(?:\.\d+)?|lo\d+(?:\.\d+)?|[^\W_]+(?:[.\-][^\W_]+)*|[^\s]", re.UNICODE)

def tokenize(text):
    if not isinstance(text, str):
        raise TypeError("sentence must be a string")
    text = unicodedata.normalize("NFC", text).casefold()
    # Different typography of the same hyphen, not accent stripping.
    text = text.translate(str.maketrans({"–": "-", "—": "-", "‑": "-"}))
    return tuple(_TOKEN.findall(text))

def detokenize(tokens):
    text = " ".join(tokens)
    text = re.sub(r"\s+([?,.!:;])", r"\1", text)
    text = re.sub(r"\s*/\s*", "/", text)
    return text[:1].upper() + text[1:]

def normalized_text(text):
    return detokenize(tokenize(text))
