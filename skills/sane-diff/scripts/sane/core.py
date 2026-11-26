"""Shared constants and small helpers."""
import html

# How much attention a change needs, most first. The plan uses these names.
TIERS = ["important", "attention", "supporting", "tests", "other"]
TIER_RANK = {t: i for i, t in enumerate(TIERS)}
TIER_LABEL = {"important": "Important", "attention": "Attention", "supporting": "Supporting",
              "tests": "Tests", "other": "Other"}
OLD_TIER_NAMES = {"core": "important", "risk": "attention", "noise": "other"}  # still accepted


def tier_of(name):
    """Normalize a tier name from a plan; unknown names become 'supporting'."""
    name = OLD_TIER_NAMES.get(name, name)
    return name if name in TIER_RANK else "supporting"


SEVERITY = {"must": "Must fix", "should": "Should fix", "nit": "Nit", "question": "Question"}
SEVERITY_ORDER = ["must", "should", "question", "nit"]

FINDING_LABEL = {"security": "Security", "logic": "Logic", "performance": "Performance"}
DEFAULT_MIN_SCORE = 7

WHOLE_FILE = (0, 10 ** 9)


def esc(text):
    """HTML-escape any value (None becomes an empty string)."""
    return html.escape("" if text is None else str(text), quote=True)
