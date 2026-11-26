"""Split a diff into reviewable groups, and keep track of what is done on disk.

Small PRs (up to MAX_LINES changed lines and MAX_FILES files, not counting mechanical
files) become one group, shown as one page. Bigger PRs are split by project (nx
project.json, else package.json, else apps/x, libs/x ...), and further by folder when
a project is still too big. Lockfiles, generated files and whitespace-only changes go
into one 'mechanical' group that is listed, never reviewed by the AI.
"""
import json
import os
import re
import sys

from .diffparse import counts, parse, split_raw

STATE_DIR = ".sane-diff"
GROUPS_DIR = os.path.join(STATE_DIR, "groups")
STATE_FILE = os.path.join(STATE_DIR, "groups.json")

MAX_LINES, MAX_FILES = 5000, 100      # one review handles at most this much
TINY_LINES = 50                       # projects smaller than this are merged together

LOCKFILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json", "Podfile.lock",
             "Gemfile.lock", "Cargo.lock", "poetry.lock", "composer.lock", "go.sum", "Package.resolved",
             "gradle.lockfile", "bun.lockb", "uv.lock", "Pipfile.lock", "flake.lock"}
GENERATED = re.compile(
    r"(^|/)(__generated__|generated|gen|dist|build|out|coverage|vendor|node_modules|__snapshots__)/"
    r"|\.(min\.js|min\.css|map|snap|g\.dart|pb\.go|pb\.swift|lock)$|_pb2\.py$|\.generated\.")
OWN_OUTPUT = re.compile(r"\.(sane|big|better)-diff/")


# ---------------------------------------------------------------- classifying files

def mechanical_reason(f):
    """Why a file needs no human-style review, or None if it does."""
    path, name = f["path"], os.path.basename(f["path"])
    if f["binary"]:
        return "binary"
    if name in LOCKFILES:
        return "lockfile"
    if GENERATED.search(path):
        return "generated"
    removed = "".join(l[3] for h in f["hunks"] for l in h["lines"] if l[0] == "del")
    added = "".join(l[3] for h in f["hunks"] for l in h["lines"] if l[0] == "add")
    if (removed or added) and "".join(removed.split()) == "".join(added.split()):
        return "whitespace only"
    if f["status"] == "renamed" and not f["hunks"]:
        return "renamed, no changes"
    return None


def project_of(path):
    """The project a file belongs to: nearest project.json, then package.json, then a path guess."""
    for marker in ("project.json", "package.json"):
        folder = os.path.dirname(path)
        while folder:
            if os.path.exists(os.path.join(folder, marker)):
                return folder
            folder = os.path.dirname(folder)
    parts = path.split("/")
    if parts[0] in ("apps", "libs", "packages", "modules", "services") and len(parts) > 2:
        return "/".join(parts[:2])
    return parts[0] if len(parts) > 1 else "(root files)"


def lines_in(files):
    return sum(f["add"] + f["del"] for f in files)


def fits(files):
    return lines_in(files) <= MAX_LINES and len(files) <= MAX_FILES


def chunk(files, label):
    """Cut a list of files into consecutive parts that each fit in one review."""
    parts, current = [], []
    for f in files:
        if current and not fits(current + [f]):
            parts.append(current); current = []
        current.append(f)
    parts.append(current)
    if len(parts) == 1:
        return [(label, parts[0])]
    return [(f"{label} (part {k}/{len(parts)})", p) for k, p in enumerate(parts, 1)]


def by_folder(label, files, depth):
    """Split a group that is too big by the next folder level, recursively."""
    if fits(files) or len(files) == 1:
        return [(label, files)]
    buckets = {}
    for f in files:
        folders = f["path"].split("/")[:-1]
        buckets.setdefault("/".join(folders[:depth]) or "(root files)", []).append(f)
    if len(buckets) == 1:
        deepest = max(len(f["path"].split("/")) - 1 for f in files)
        if depth < deepest:
            return by_folder(label, files, depth + 1)
        return chunk(sorted(files, key=lambda f: f["path"]), label)
    result = []
    for key, part in sorted(buckets.items(), key=lambda kv: (-lines_in(kv[1]), kv[0])):
        result += by_folder(key, part, depth + 1)
    return result


# ---------------------------------------------------------------- splitting

def split(diff_file):
    """Read the whole diff, decide the groups, write one .diff per group and the state file."""
    text = open(diff_file, encoding="utf-8", errors="replace").read()
    review, mechanical = [], []
    for raw in split_raw(text):
        parsed = parse(raw)
        if not parsed or OWN_OUTPUT.match(parsed[0]["path"]):
            continue
        f = parsed[0]
        add, dele = counts(f)
        entry = {"path": f["path"], "raw": raw, "add": add, "del": dele, "reason": mechanical_reason(f)}
        (mechanical if entry["reason"] else review).append(entry)

    single = fits(review)
    if single:
        groups = [("whole PR", review)] if review else []
    else:
        projects = {}
        for f in review:
            projects.setdefault(project_of(f["path"]), []).append(f)
        groups = []
        for project, files in projects.items():
            depth = len(project.split("/")) + 1 if project != "(root files)" else 1
            groups += by_folder(project, files, depth)
        tiny = [g for g in groups if lines_in(g[1]) < TINY_LINES]
        if len(tiny) >= 2:
            groups = [g for g in groups if lines_in(g[1]) >= TINY_LINES]
            files = [f for _label, part in sorted(tiny, key=lambda g: g[0]) for f in part]
            n_projects = len({project_of(f["path"]) for f in files})
            groups += chunk(files, f"small changes in {n_projects} projects")
        groups.sort(key=lambda g: (-lines_in(g[1]), g[0]))
    if mechanical:
        groups.append(("mechanical", mechanical))

    if os.path.isdir(GROUPS_DIR):
        for name in os.listdir(GROUPS_DIR):
            os.remove(os.path.join(GROUPS_DIR, name))
    os.makedirs(GROUPS_DIR, exist_ok=True)
    width = max(2, len(str(len(groups))))
    state = {"source": diff_file, "single": single, "groups": []}
    for n, (name, files) in enumerate(groups, 1):
        gid = str(n).zfill(width)
        with open(os.path.join(GROUPS_DIR, gid + ".diff"), "w", encoding="utf-8") as out:
            out.write("".join(f["raw"] for f in files))
        state["groups"].append({
            "n": n, "id": gid, "name": name, "kind": "mechanical" if name == "mechanical" else "review",
            "files": len(files), "add": sum(f["add"] for f in files), "del": sum(f["del"] for f in files),
            "list": [[f["path"], f["add"], f["del"], f["reason"]] for f in files]})
    save_state(state)
    return state


# ---------------------------------------------------------------- state on disk

def save_state(state):
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), indent=1)


def load_state():
    if not os.path.exists(STATE_FILE):
        sys.exit("Nothing prepared yet. Run the 'prepare' command first.")
    return json.load(open(STATE_FILE, encoding="utf-8"))


def group_file(g, ext):
    return os.path.join(GROUPS_DIR, g["id"] + ext)


def has_review(g):
    if g["kind"] == "mechanical":
        return os.path.exists(group_file(g, ".html"))
    return os.path.exists(group_file(g, ".plan.json"))


def has_security(g):
    return os.path.exists(group_file(g, ".sec.json"))


def review_groups(state):
    return [g for g in state["groups"] if g["kind"] == "review"]


def mechanical_group(state):
    return next((g for g in state["groups"] if g["kind"] == "mechanical"), None)


def next_to_review(state):
    return next((g for g in review_groups(state) if not has_review(g)), None)


def next_without_security(state):
    return next((g for g in state["groups"] if not has_security(g)), None)


def find_group(state, ref):
    ref = str(ref).strip()
    number = re.fullmatch(r"(?:group-)?0*(\d+)", ref)
    for g in state["groups"]:
        if (number and g["n"] == int(number.group(1))) or g["name"] == ref:
            return g
    sys.exit(f"No group '{ref}'. Run the 'status' command to see the groups.")


def print_groups(state, header=None):
    groups = state["groups"]
    if header:
        print(header)
    width = max((len(g["name"]) for g in groups), default=10)
    for g in groups:
        done = "·" if g["kind"] == "mechanical" else ("✓" if has_review(g) else " ")
        checked = "sec" if has_security(g) else "   "
        note = "  (lockfiles, generated, whitespace: listed, not reviewed)" if g["kind"] == "mechanical" else ""
        print(f" {done} {checked} {g['n']:>3}  {g['name']:<{width}}  {g['files']:>4} files  +{g['add']} −{g['del']}{note}")
    print("  ✓ = reviewed   sec = security pass done")


# ---------------------------------------------------------------- security findings

def load_findings(g, min_score):
    """Security findings of a group, sorted by score; only those >= min_score are shown."""
    path = group_file(g, ".sec.json")
    if not os.path.exists(path):
        return None
    findings = sorted(json.load(open(path, encoding="utf-8")).get("findings", []),
                      key=lambda x: -float(x.get("score", 0)))
    shown, hidden = [], 0
    for k, x in enumerate(findings, 1):
        score = float(x.get("score", 0))
        if score < min_score:
            hidden += 1
            continue
        category = x.get("category", "security")
        details = [
            (("Attack: " if category == "security" else "When: ") + x["scenario"]) if x.get("scenario") else "",
            x.get("more", ""),
            ("Fix: " + x["fix"]) if x.get("fix") else "",
            ("Confidence: " + x["confidence"]) if x.get("confidence") else ""]
        shown.append({"_id": f"#{k}", "file": x.get("file"), "line": x.get("line"), "text": x.get("text", ""),
                      "more": " · ".join(d for d in details if d), "comment": x.get("comment", ""),
                      "category": category, "score": int(score) if score == int(score) else score,
                      "severity": "must" if score >= 9 else "should" if score >= 7 else "question"})
    return {"shown": shown, "hidden": hidden, "min": f"{float(min_score):g}", "total": len(findings)}
