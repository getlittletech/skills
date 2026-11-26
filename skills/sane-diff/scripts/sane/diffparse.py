"""Reading unified diffs: files, hunks, lines, and word-level changes."""
import difflib
import re

from .core import esc
from .symbols import lk

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")
TOKEN_RE = re.compile(r"\w+|\s+|[^\w\s]")


def parse(text):
    files, f, h = [], None, None
    o = n = 0
    for line in text.splitlines():
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.*) b/(.*)$", line)
            f = {"old": m.group(1) if m else "", "new": m.group(2) if m else "",
                 "status": "modified", "binary": False, "hunks": []}
            files.append(f); h = None; continue
        if f is None:
            continue
        m = HUNK_RE.match(line)
        if m:
            o, n = int(m.group(1)), int(m.group(3))
            h = {"header": line, "lines": [], "start": n,
                 "end": n + max(int(m.group(4) or 1), 1) - 1}
            f["hunks"].append(h); continue
        if h is None:
            if line.startswith("new file mode"): f["status"] = "added"
            elif line.startswith("deleted file mode"): f["status"] = "deleted"
            elif line.startswith("rename from "): f["status"] = "renamed"; f["old"] = line[12:]
            elif line.startswith("rename to "): f["new"] = line[10:]
            elif line.startswith("Binary files"): f["binary"] = True
            continue
        # line: [type, old_no, new_no, text, pos]   pos = new-side position (also for deletions)
        if line.startswith("+"):
            h["lines"].append(["add", None, n, line[1:], n]); n += 1
        elif line.startswith("-"):
            h["lines"].append(["del", o, None, line[1:], n]); o += 1
        elif line.startswith("\\"):
            pass
        else:
            h["lines"].append(["ctx", o, n, line[1:], n]); o += 1; n += 1
    for i, f in enumerate(files):
        f["path"] = f["old"] if f["status"] == "deleted" else f["new"]
        f["fi"] = i
        for j, h in enumerate(f["hunks"]):
            h["hid"] = f"{i}-{j}"
    return files


def word_diff(a, b):
    ta, tb = TOKEN_RE.findall(a), TOKEN_RE.findall(b)
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    if sm.ratio() < 0.3:
        return (f'<span class="wd">{lk(a)}</span>' if a.strip() else esc(a),
                f'<span class="wa">{lk(b)}</span>' if b.strip() else esc(b))
    oa, ob = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        x, y = "".join(ta[i1:i2]), "".join(tb[j1:j2])
        if op == "equal":
            oa.append(lk(x)); ob.append(lk(y)); continue
        if x:
            oa.append(f'<span class="wd">{lk(x)}</span>' if x.strip() else esc(x))
        if y:
            ob.append(f'<span class="wa">{lk(y)}</span>' if y.strip() else esc(y))
    return "".join(oa), "".join(ob)


def pair_lines(L, d, a):
    rows, j = [], 0
    for di in d:
        best, bj = 0.0, None
        for k in range(j, len(a)):
            r = difflib.SequenceMatcher(None, L[di][3].strip(), L[a[k]][3].strip(), autojunk=False).ratio()
            if r > best:
                best, bj = r, k
        if bj is not None and best >= 0.5:
            rows += [(None, a[k]) for k in range(j, bj)]
            rows.append((di, a[bj])); j = bj + 1
        else:
            rows.append((di, None))
    rows += [(None, a[k]) for k in range(j, len(a))]
    return rows


def segments(lines):
    out, i = [], 0
    while i < len(lines):
        if lines[i][0] == "ctx":
            out.append(("ctx", [i])); i += 1; continue
        d, a = [], []
        while i < len(lines) and lines[i][0] == "del":
            d.append(i); i += 1
        while i < len(lines) and lines[i][0] == "add":
            a.append(i); i += 1
        out.append(("chg", d, a))
    return out



def split_raw(text):
    """Split a unified diff into per-file raw chunks."""
    chunks, cur = [], []
    for line in text.splitlines(keepends=True):
        if line.startswith("diff --git ") and cur:
            chunks.append("".join(cur)); cur = []
        cur.append(line)
    if cur and "".join(cur).startswith("diff --git "):
        chunks.append("".join(cur))
    return chunks


def counts(f):
    add = sum(1 for h in f["hunks"] for l in h["lines"] if l[0] == "add")
    dele = sum(1 for h in f["hunks"] for l in h["lines"] if l[0] == "del")
    return add, dele


