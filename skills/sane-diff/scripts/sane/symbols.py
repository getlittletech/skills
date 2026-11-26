"""Find function and class definitions in the diff, so their names can link to them."""
import re

from .core import esc

DEF_PATTERNS = [
    re.compile(r"\bfunction\s*\*?\s*([A-Za-z_$][\w$]*)"),
    re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*(?::[^=]+)?=>"),
    re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?function\b"),
    re.compile(r"\b(?:func|fun|def)\s+(?:self\.)?([A-Za-z_]\w*[?!]?)"),
    re.compile(r"\bfunc\s+\([^)]*\)\s*([A-Za-z_]\w*)"),
    re.compile(r"\b(?:class|struct|interface|enum|protocol|trait|type|module)\s+([A-Za-z_]\w*)"),
    re.compile(r"^\s*(?:export\s+)?(?:public\s+|private\s+|protected\s+|static\s+|async\s+|override\s+)*"
               r"([A-Za-z_$][\w$]*)\s*\([^()]*\)\s*(?::\s*[^{=]+)?\{\s*$"),
]
NOT_DEFS = {"if", "for", "while", "switch", "catch", "return", "function", "constructor",
            "render", "get", "set", "init", "main", "test", "it", "describe", "default",
            "new", "else", "elsif", "do", "end", "then", "with", "type", "self", "this"}
IDENT_RE = re.compile(r"[A-Za-z_$][\w$]*[?!]?")
DEFS = {}  # name -> "file:line"


def defs_on_line(text):
    out = []
    for p in DEF_PATTERNS:
        for m in p.finditer(text):
            nm = m.group(1)
            if nm not in NOT_DEFS and len(nm) >= 3 and nm not in out:
                out.append(nm)
    return out


def collect_defs(files):
    seen = {}
    for f in files:
        for h in f["hunks"]:
            for l in h["lines"]:
                if l[2] is None:
                    continue
                for nm in defs_on_line(l[3]):
                    seen.setdefault(nm, []).append(f"{f['path']}:{l[2]}")
    DEFS.clear()
    for nm, where in seen.items():
        DEFS[nm] = where[0]


def lk(text):
    """Escape code text and turn known function/class names into jump links."""
    if not DEFS:
        return esc(text)
    out, last = [], 0
    for m in IDENT_RE.finditer(text):
        out.append(esc(text[last:m.start()]))
        nm = m.group()
        if nm in DEFS:
            out.append(f'<a class="sym" data-sym="{esc(nm)}" title="Go to {esc(DEFS[nm])}">{esc(nm)}</a>')
        else:
            out.append(esc(nm))
        last = m.end()
    out.append(esc(text[last:]))
    return "".join(out)


