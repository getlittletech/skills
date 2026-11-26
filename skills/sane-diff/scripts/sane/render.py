"""Build the review page (HTML) from a parsed diff, a plan and security findings."""
import json
import os

from .core import (DEFAULT_MIN_SCORE, FINDING_LABEL, SEVERITY, SEVERITY_ORDER, TIER_LABEL, TIER_RANK,
                   TIERS, WHOLE_FILE, esc, tier_of)
from .diffparse import pair_lines, segments, word_diff
from .symbols import DEFS, collect_defs, defs_on_line, lk
from .groups import group_file, has_review, has_security, review_groups

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def page_template():
    def read(name):
        return open(os.path.join(ASSETS, name), encoding="utf-8").read()
    return read("page.html").replace("%CSS%", read("page.css")).replace("%JS%", read("page.js"))


def tag(text, kind):
    return f'<span class="tag t-{kind}">{esc(text)}</span>'


def ann_html(a, kind):
    """One folded line: a small text tag, the number, the text; details open on click."""
    number = f'<b class="aid">{esc(a["_id"])}</b>' if a.get("_id") else ""
    if kind == "note":
        is_doc = a.get("kind") == "doc"
        cls, label = "note" + (" doc" if is_doc else ""), tag("What it does" if is_doc else "Note", "doc" if is_doc else "note")
    elif kind == "mismatch":
        cls, label = "sev-question", tag("Not as described", "question")
    elif "score" in a:
        sev = a.get("severity", "should")
        cls = f"sev-{sev} secf"
        label = tag(f'{FINDING_LABEL.get(a.get("category"), "Security")} {a["score"]}', sev)
    else:
        sev = a.get("severity", "should")
        cls, label = f"sev-{sev}", tag(SEVERITY.get(sev, "Should fix"), sev)
    head = f'{label}{number}<span class="at">{esc(a.get("text"))}</span>'
    more = a.get("more") or a.get("detail") or ""
    comment = a.get("comment") or ""
    aid = f' data-issue="{esc(a["_id"])}"' if a.get("_id") else ""
    if not more and not comment:
        return f'<div class="ann {cls} flat"{aid}>{head}</div>'
    body = f'<div class="am">{esc(more)}</div>' if more else ""
    if comment:
        body += (f'<div class="ac"><span>{esc(comment)}</span>'
                 f'<button class="copy" data-copy="{esc(comment)}">Copy</button></div>')
    return f'<details class="ann {cls}"{aid}><summary>{head}</summary>{body}</details>'


def count_pill(issues):
    """Small count of issues, colored by the most serious one."""
    if not issues:
        return ""
    worst = next(s for s in SEVERITY_ORDER + ["should"] if any(i.get("severity", "should") == s for i in issues))
    return f'<span class="nc sev-{worst}" title="{len(issues)} issue{"s" if len(issues) != 1 else ""}">{len(issues)}</span>'


def badge(st):
    return (f'<a class="sb x-{st["tier"]}" data-go-story="{st["n"]}" '
            f'title="Story {st["n"]} · {esc(TIER_LABEL[st["tier"]])}: {esc(st.get("title"))}">'
            f'{st["n"]}<span>{TIER_LABEL[st["tier"]]}</span></a>')


def label_html(st, r, anchor=""):
    """Folded one-line label above a block: story badge + what the block does."""
    text = r.get("explain") or st.get("title", "")
    more = r.get("more", "")
    aid = f' id="{anchor}"' if anchor else ""
    head = f'{badge(st)}<span class="at">{esc(text)}</span>'
    inner = (f'<details class="ann ex x-{st["tier"]}"><summary>{head}</summary><div class="am">{esc(more)}</div></details>'
             if more else f'<div class="ann ex flat x-{st["tier"]}">{head}</div>')
    return f'<div class="lbl"{aid}>{inner}</div>'


# ------------------------------------------------------------------ file rendering
def render_hunks(f, hunks, owner, stories, focus, anns, labels):
    """Render hunks of one file as a unified table (.u) and a side-by-side table (.s).
    owner: {(hid, li): (story_n, range_idx)}; focus: story n (story view) or None (file view);
    labels: {(hid, li): [html]} placed above the block they describe; anns: [(kind, a)].
    In story view, lines far from the focused story collapse into a '⋯ N lines' row."""
    by_line = {}
    for kind, a in anns:
        by_line.setdefault(a.get("line"), []).append((kind, a))
    U, S = [], []

    def full(x, extra=""):
        return (f'<tr class="ar{extra}"><td colspan="3">{x}</td></tr>',
                f'<tr class="ar{extra}"><td colspan="5">{x}</td></tr>')

    def both(pair):
        U.append(pair[0]); S.append(pair[1])

    # which lines to show
    keep = {}
    for h in hunks:
        L = h["lines"]
        if focus is None:
            keep[h["hid"]] = set(range(len(L)))
            continue
        base = [li for li in range(len(L)) if owner.get((h["hid"], li), (0,))[0] == focus]
        keep[h["hid"]] = {k for li in base for k in range(li - 2, li + 3) if 0 <= k < len(L)}
    visible = {h["lines"][li][2] for h in hunks for li in keep[h["hid"]] if h["lines"][li][2] is not None}

    for x in labels.get("top", []):
        both(full(x, " ex-row"))
    for ln in [k for k in by_line if k is None or k not in visible]:
        for kind, a in by_line[ln]:
            a2 = a if ln is None else dict(a, text=f'(line {ln}) {a.get("text", "")}')
            both(full(ann_html(a2, kind)))
    used_u, used_s = set(), set()

    def anns_after(nn, used):
        if nn is None or nn not in by_line or nn in used:
            return []
        used.add(nn)
        return [ann_html(a, k) for k, a in by_line[nn]]

    def cls_of(h, li):
        l = h["lines"][li]
        if l[0] == "ctx":
            return "ctx"
        o = owner.get((h["hid"], li))
        if o is None:
            return l[0] + " off un"
        st = stories[o[0] - 1]
        if st["ranges"][o[1]].get("grey"):
            return l[0] + " off"
        if focus is not None and o[0] != focus:
            return l[0] + " off other"
        return f'{l[0]} x-{st["tier"]}'

    def defattr(l):
        if l[2] is None:
            return ""
        d = [nm for nm in defs_on_line(l[3]) if nm in DEFS]
        return f' data-def="{esc(d[0])}"' if d else ""

    skip = {"u": 0, "s": 0}

    def flush(which):
        n = skip[which]
        if n:
            row = (f'<tr class="gaprow"><td colspan="{3 if which == "u" else 5}">⋯ {n} line{"s" if n > 1 else ""}'
                   f' not in this story</td></tr>')
            (U if which == "u" else S).append(row)
            skip[which] = 0

    for h in sorted(hunks, key=lambda x: x["start"]):
        hdr = esc(h["header"].split("@@")[-1].strip()) or "&nbsp;"
        both((f'<tr class="hh"><td colspan="3">{hdr}<span class="hl">line {h["start"]}</span></td></tr>',
              f'<tr class="hh"><td colspan="5">{hdr}<span class="hl">line {h["start"]}</span></td></tr>'))
        L, K, hid = h["lines"], keep[h["hid"]], h["hid"]
        for seg in segments(L):
            if seg[0] == "ctx":
                li = seg[1][0]
                if li not in K:
                    skip["u"] += 1; skip["s"] += 1; continue
                flush("u"); flush("s")
                _t, o, nn, text, _p = L[li]
                for x in labels.get((hid, li), []):
                    both(full(x, " ex-row"))
                code = lk(text) or " "
                da = defattr(L[li])
                U.append(f'<tr class="ctx"{da}><td class="ln">{nn}</td><td class="sg"></td><td class="cd">{code}</td></tr>')
                S.append(f'<tr class="ctx"{da}><td class="ln">{o}</td><td class="cd">{code}</td>'
                         f'<td class="ln">{nn}</td><td class="cd">{code}</td><td class="sp"></td></tr>')
                for x in anns_after(nn, used_u):
                    U.append(full(x)[0])
                for x in anns_after(nn, used_s):
                    S.append(full(x)[1])
                continue
            _k, d, a = seg
            pairs = pair_lines(L, d, a)
            mk = {}
            for di, ai in pairs:
                if di is not None and ai is not None:
                    mk[di], mk[ai] = word_diff(L[di][3], L[ai][3])
                for li in (di, ai):
                    if li is not None and li not in mk:
                        mk[li] = f'<span class="nl">{lk(L[li][3])}</span>' if L[li][3].strip() else " "
            # unified: removed lines first, then added lines; labels right above their first line
            for li in d + a:
                if li not in K:
                    skip["u"] += 1; continue
                flush("u")
                for x in labels.get((hid, li), []):
                    U.append(full(x, " ex-row")[0])
                l = L[li]
                num = l[2] if l[2] is not None else l[1]
                sign = "+" if l[0] == "add" else "−"
                U.append(f'<tr class="{cls_of(h, li)}"{defattr(l)}><td class="ln">{num}</td><td class="sg">{sign}</td>'
                         f'<td class="cd">{mk[li] or " "}</td></tr>')
                for x in anns_after(l[2], used_u):
                    U.append(full(x)[0])
            # side by side: each label goes above the first row that holds a line of its block
            row_labels = {}
            for li in d + a:
                if (hid, li) not in labels:
                    continue
                o = owner.get((hid, li))
                target = 0
                for k, (di, ai) in enumerate(pairs):
                    if any(x is not None and owner.get((hid, x)) == o for x in (di, ai)):
                        target = k; break
                row_labels.setdefault(target, []).extend(labels[(hid, li)])
            for k, (di, ai) in enumerate(pairs):
                if not any(x is not None and x in K for x in (di, ai)):
                    skip["s"] += 1; continue
                flush("s")
                for x in row_labels.get(k, []):
                    S.append(full(x, " ex-row")[1])
                if di is not None:
                    c = cls_of(h, di)
                    left = f'<td class="ln {c}">{L[di][1]}</td><td class="cd {c}">{mk[di] or " "}</td>'
                else:
                    left = '<td class="ln gap"></td><td class="cd gap"></td>'
                if ai is not None:
                    c = cls_of(h, ai)
                    right = f'<td class="ln {c}">{L[ai][2]}</td><td class="cd {c}">{mk[ai] or " "}</td>'
                else:
                    right = '<td class="ln gap"></td><td class="cd gap"></td>'
                da = defattr(L[ai]) if ai is not None else ""
                S.append(f'<tr class="sr"{da}>{left}{right}<td class="sp"></td></tr>')
                if ai is not None:
                    for x in anns_after(L[ai][2], used_s):
                        S.append(full(x)[1])
        flush("u"); flush("s")
    return (f'<table class="d u"><colgroup><col class="c-ln"><col class="c-sg"><col></colgroup>{"".join(U)}</table>'
            f'<table class="d s"><colgroup><col class="c-ln"><col><col class="c-ln"><col><col class="c-sp"></colgroup>'
            f'{"".join(S)}</table>')


# ------------------------------------------------------------------ page
def render_page(files, plan, nav="", key="", sec=None, appendix=""):
    """The full review page. nav: group bar (big PRs); appendix: HTML added at the end of both views."""
    collect_defs(files)
    idx = {}
    for f in files:
        for k in (f["path"], f["new"], f["old"]):
            idx[k] = f
    warn = []

    raw = plan.get("stories") or plan.get("steps") or []
    stories = []
    for st in raw:
        st = dict(st)
        st["tier"] = tier_of(st.get("tier"))
        st.setdefault("ranges", []); st.setdefault("notes", []); st.setdefault("issues", [])
        stories.append(st)
    # most important first (stable: the agent's order is kept within a tier)
    stories.sort(key=lambda s: TIER_RANK[s["tier"]])
    c = 0
    for n, st in enumerate(stories, 1):
        st["n"] = n
        for i in st["issues"]:
            c += 1; i["_id"] = f"#{c}"
        for r in st["ranges"]:
            f = idx.get(r.get("file"))
            if not f:
                warn.append(f'story {n}: file not in diff: {r.get("file")}')
                r["_f"] = None; continue
            r["_f"] = f["fi"]
            s, e = r.get("start"), r.get("end")
            if s is None or f["status"] == "deleted":
                s, e = WHOLE_FILE
            r["_s"], r["_e"] = s, (s if e is None else e)

    # ---- who owns each changed line: first matching story (most important wins)
    owner = {}
    for f in files:
        for h in f["hunks"]:
            for li, l in enumerate(h["lines"]):
                if l[0] == "ctx":
                    continue
                pos = l[4]
                hit = None
                for st in stories:
                    for ri, r in enumerate(st["ranges"]):
                        if r.get("_f") != f["fi"]:
                            continue
                        hi = r["_e"] + (1 if l[0] == "del" else 0)
                        if r["_s"] <= pos <= hi:
                            hit = (st["n"], ri); break
                    if hit:
                        break
                if hit:
                    owner[(h["hid"], li)] = hit
            # forgotten lines next to a covered block join that block
            L = h["lines"]; i = 0
            while i < len(L):
                if L[i][0] == "ctx":
                    i += 1; continue
                j = i
                while j < len(L) and L[j][0] != "ctx":
                    j += 1
                run_ = list(range(i, j))
                prev = None
                for li in run_:
                    if (h["hid"], li) in owner:
                        prev = owner[(h["hid"], li)]
                    elif prev:
                        owner[(h["hid"], li)] = prev
                nxt = None
                for li in reversed(run_):
                    if (h["hid"], li) in owner:
                        nxt = owner[(h["hid"], li)]
                    elif nxt:
                        owner[(h["hid"], li)] = nxt
                i = j

    # a removed line belongs to the same story as the new line that replaced it
    for f in files:
        for h in f["hunks"]:
            for seg in segments(h["lines"]):
                if seg[0] != "chg":
                    continue
                for di, ai in pair_lines(h["lines"], seg[1], seg[2]):
                    if di is not None and ai is not None and (h["hid"], ai) in owner:
                        owner[(h["hid"], di)] = owner[(h["hid"], ai)]

    uncovered = {}
    for f in files:
        for h in f["hunks"]:
            for li, l in enumerate(h["lines"]):
                if l[0] != "ctx" and (h["hid"], li) not in owner:
                    uncovered[f["path"]] = uncovered.get(f["path"], 0) + 1
    if sec is not None:
        for k, f_ in enumerate(sec["shown"], 1):
            f_["_id"] = f"#{c + k}"
    sec_only = sec is not None and not stories
    if not sec_only:
        for p, cnt in uncovered.items():
            warn.append(f"{cnt} changed lines in {p} are not in any story")
    shown = (sec or {}).get("shown", [])
    for a in shown:
        if not idx.get(a.get("file")):
            warn.append(f'security finding {a["_id"]}: file not in this group: {a.get("file")}')

    def owner_of_line(f, line):
        for h in f["hunks"]:
            for li, l in enumerate(h["lines"]):
                if l[2] == line:
                    o = owner.get((h["hid"], li))
                    return o[0] if o else None
        return None

    # ---- per file: which stories, how many lines, order
    touch = {}  # (n, fi) -> changed line count
    for (hid, li), (n, ri) in owner.items():
        fi = int(hid.split("-")[0])
        touch[(n, fi)] = touch.get((n, fi), 0) + 1
    for st in stories:
        st["_lines"] = sum(v for (n, _fi), v in touch.items() if n == st["n"])

    def file_key(f):
        ks = [(TIER_RANK[stories[n - 1]["tier"]], n) for (n, fi) in touch if fi == f["fi"]]
        return min(ks) if ks else (99, 0)
    forder = sorted(files, key=file_key)
    top = {}
    if sec_only:  # no review yet: files with the highest-scored findings first
        for a in shown:
            f = idx.get(a.get("file"))
            if f:
                top[f["fi"]] = max(top.get(f["fi"], 0), a["score"])
        forder = sorted(files, key=lambda f: -top.get(f["fi"], 0))
    best_tier = {}
    for f in files:
        k = file_key(f)
        best_tier[f["fi"]] = TIERS[k[0]] if k[0] < 99 else "other"

    # ---- labels: one per range, anchored at its first owned line
    def labels_for(f, hunks, story_filter):
        lab = {}
        anchored = set()
        for st in stories:
            if story_filter is not None and st["n"] != story_filter:
                continue
            for ri, r in enumerate(st["ranges"]):
                if r.get("_f") != f["fi"] or r.get("grey"):
                    continue
                first = None
                for h in sorted(hunks, key=lambda x: x["start"]):
                    for li in range(len(h["lines"])):
                        if owner.get((h["hid"], li)) == (st["n"], ri):
                            first = (h["hid"], li); break
                    if first:
                        break
                if first is None:
                    continue
                pre = "f" if story_filter is None else "s"
                anchor = f'{pre}{f["fi"]}-{st["n"]}' if st["n"] not in anchored else ""
                anchored.add(st["n"])
                lab.setdefault(first, []).append(label_html(st, r, anchor))
        return lab

    def anns_for(f, story_filter):
        out = []
        for st in stories:
            if story_filter is not None and st["n"] != story_filter:
                continue
            for a in st["notes"]:
                if idx.get(a.get("file")) is f:
                    out.append(("note", a))
            for a in st["issues"]:
                if idx.get(a.get("file")) is f:
                    out.append(("issue", a))
        for a in shown:
            if idx.get(a.get("file")) is f and (story_filter is None or owner_of_line(f, a.get("line")) == story_filter):
                out.append(("issue", a))
        return out

    def fname(f):
        return f["path"] if f["status"] != "renamed" else f'{f["old"]} → {f["new"]}'

    def status_badge(f):
        return "" if f["status"] == "modified" else f'<span class="badge">{esc(f["status"])}</span>'

    # ---- BY FILE view
    fsecs, fnav = [], []
    for f in forder:
        fi = f["fi"]
        sts = sorted({n for (n, x) in touch if x == fi})
        t = best_tier[fi]
        changed = sum(1 for h in f["hunks"] for l in h["lines"] if l[0] != "ctx")
        badges = "".join(f'<a class="sb x-{stories[n-1]["tier"]}" data-go-cell="{n},{fi}" '
                         f'title="{esc(stories[n-1].get("title"))}">{n}</a>' for n in sts)
        if f["binary"]:
            body = '<div class="muted">Binary file</div>'
        else:
            body = render_hunks(f, f["hunks"], owner, stories, None, anns_for(f, None),
                                labels_for(f, f["hunks"], None))
        body = f'<div class="file">' + (f'<div class="fh">{status_badge(f)}</div>' if status_badge(f) else "") + f'{body}</div>'
        fold = (fi not in top) if sec_only else (t == "other" or not sts)
        if fold:
            body = f'<details class="fold"><summary>Show {changed} changed lines</summary>{body}</details>'
        fsecs.append(f'<section class="sec fs x-{t}" id="file-{fi}" data-t="{t}" data-k="file-{fi}">'
                     f'<div class="sh"><span class="tb">{TIER_LABEL[t] if sts else ("Not reviewed" if sec_only else "Unassigned")}</span>'
                     f'<h2 class="mono">{esc(fname(f))}</h2><span class="sbs">{badges}</span>'
                     f'<span class="cnt">{changed} lines</span>'
                     f'<label class="dn"><input type="checkbox" data-k="file-{fi}">done</label></div>{body}</section>')
        here = [i for st in stories for i in st["issues"] if idx.get(i.get("file")) is f]
        worst = count_pill(here)
        fnav.append(f'<a class="nv x-{t}" data-go-file="{fi}" data-k="file-{fi}" data-t="{t}"><i></i>'
                    f'<span class="nt mono">{esc(os.path.basename(f["path"]))}</span>{worst}</a>')

    # ---- BY STORY view
    ssecs, snav = [], []
    for st in stories:
        n, t = st["n"], st["tier"]
        order = []
        for r in st["ranges"]:
            if r.get("_f") is not None and r["_f"] not in order and touch.get((n, r["_f"])):
                order.append(r["_f"])
        blocks = []
        for fi in order:
            f = files[fi]
            hs = [h for h in f["hunks"] if any(owner.get((h["hid"], li), (0,))[0] == n
                                               for li in range(len(h["lines"])))]
            inner = render_hunks(f, hs, owner, stories, n, anns_for(f, n), labels_for(f, hs, n))
            blocks.append(f'<div class="file" id="s{fi}-{n}x"><div class="fh mono">{esc(fname(f))}{status_badge(f)}'
                          f'<a class="whole" data-go-cell="{n},{fi}" data-mode="file">whole file ↗</a></div>{inner}</div>')
        lead = ""
        if st.get("explain"):
            lead = label_html(st, {"explain": st["explain"], "more": st.get("more", "")})
        content = lead + ("".join(blocks) or '<p class="muted">No code in this story.</p>')
        if t == "other":
            content = f'<details class="fold"><summary>Show {st["_lines"]} changed lines</summary>{content}</details>'
        iss = st["issues"]
        worst = count_pill(iss)
        ssecs.append(f'<section class="sec st x-{t}" id="story-{n}" data-t="{t}" data-k="story-{n}">'
                     f'<div class="sh">{badge(st)}<h2>{esc(st.get("title"))}</h2>'
                     f'<span class="cnt">{st["_lines"]} lines</span>'
                     f'<label class="dn"><input type="checkbox" data-k="story-{n}">done</label></div>{content}</section>')
        snav.append(f'<a class="nv x-{t}" data-go-story="{n}" data-k="story-{n}" data-t="{t}"><i></i>'
                    f'<span class="nt">{n}. {esc(st.get("title"))}</span>'
                    f'{worst}</a>')

    # ---- MAP: stories (rows) x files (columns); dot size shows how many lines the story changes there
    mfiles = [f for f in forder if any(x == f["fi"] for (_n, x) in touch)]
    biggest = max(touch.values(), default=1)

    def dot(st, f):
        k = touch.get((st["n"], f["fi"]))
        if not k:
            return '<td></td>'
        size = 1 if k * 3 <= biggest else 2 if k * 3 <= biggest * 2 else 3
        return (f'<td><a class="dot d{size} x-{st["tier"]}" data-go-cell="{st["n"]},{f["fi"]}" '
                f'title="{esc(st.get("title"))} · {esc(os.path.basename(f["path"]))}: {k} lines"></a></td>')
    head_cells = "".join(f'<th class="mf"><a data-go-file="{f["fi"]}" title="{esc(f["path"])}">'
                         f'{esc(os.path.basename(f["path"]))}</a></th>' for f in mfiles)
    rows = "".join(f'<tr class="x-{st["tier"]}" data-t="{st["tier"]}"><th class="ms"><a data-go-story="{st["n"]}">'
                   f'<span class="num">{st["n"]}</span><span class="sname">{esc(st.get("title"))}</span></a></th>'
                   + "".join(dot(st, f) for f in mfiles) + '</tr>' for st in stories)
    gmap = (f'<details class="map" open><summary>Map · {len(stories)} stories × {len(mfiles)} files</summary>'
            f'<div class="mapw"><table class="matrix"><thead><tr><th></th>{head_cells}</tr></thead>'
            f'<tbody>{rows}</tbody></table></div></details>') if stories and mfiles else ""

    # ---- header
    adds = sum(1 for f in files for h in f["hunks"] for l in h["lines"] if l[0] == "add")
    dels = sum(1 for f in files for h in f["hunks"] for l in h["lines"] if l[0] == "del")
    title = plan.get("title", "Diff")
    pr = f' · <a href="{esc(plan["pr_url"])}">PR</a>' if plan.get("pr_url") else ""
    story = ""
    if plan.get("story"):
        more = plan.get("story_more", "")
        head = f'<span class="at">{esc(plan["story"])}</span>'
        story = (f'<details class="ann note"><summary>{head}</summary><div class="am">{esc(more)}</div></details>'
                 if more else f'<div class="ann note flat">{head}</div>')
    chips = []
    for s in SEVERITY_ORDER:
        for st in stories:
            for i in st["issues"]:
                if i.get("severity", "should") == s:
                    chips.append(f'<a class="chip sev-{s}" data-go-issue="{esc(i["_id"])}" title="{esc(i.get("text"))}">'
                                 f'<b>{SEVERITY[s]}</b> {esc(i["_id"])} <span>{esc(os.path.basename(i.get("file", "")))}:{esc(i.get("line", ""))}</span></a>')
    extra = [ann_html({"text": m}, "mismatch") for m in (plan.get("mismatches") or [])]
    extra += [f'<div class="warn">⚠ {esc(w)}</div>' for w in warn]
    if sec is not None:
        extra.insert(0, sec_box(sec, inline=True))
    legend = "".join(f'<button class="lg x-{t}" data-t="{t}"><i></i>{TIER_LABEL[t]}</button>' for t in TIERS)
    head = (nav + f'<header><div class="tl"><h1>{esc(title)}</h1>'
            f'<span class="meta">{len(files)} files · <b class="p">+{adds}</b> <b class="m">−{dels}</b>{pr}</span>'
            f'<span class="sw2"><span class="vw" data-sw="mode"><button data-v="file">By file</button><button data-v="story">By story</button></span>'
            f'<span class="vw" data-sw="view"><button data-v="u">Unified</button><button data-v="s">Side by side</button></span></span></div>'
            f'{story}<div class="chips">{"".join(chips)}</div>{"".join(extra)}{gmap}'
            f'<div class="legend">{legend}<span class="lgk"><span class="swa add"></span>added '
            f'<span class="swa del"></span>removed <span class="swa un"></span>not in a story · '
            f'number = story · click a tier to hide it · keys: j/k next, f file/story, s side-by-side, e explain, x done</span></div></header>')

    page = (page_template().replace("%TITLE%", esc(title))
            .replace("%NAVF%", "".join(fnav)).replace("%NAVS%", "".join(snav))
            .replace("%HEAD%", head)
            .replace("%BYFILE%", "".join(fsecs) + appendix).replace("%BYSTORY%", "".join(ssecs) + appendix)
            .replace("%KEY%", json.dumps("sane-diff:" + key + title)))
    return page, warn


def sec_box(sec, inline):
    """Summary of the security pass at the top of a page."""
    n, hid, mn = len(sec["shown"]), sec["hidden"], sec["min"]
    cats = {}
    for a in sec["shown"]:
        cats[a["category"]] = cats.get(a["category"], 0) + 1
    by = " · ".join(f'{k} {c}' for c, k in sorted(cats.items()))
    hidden = f' · {hid} lower-scored hidden' if hid else ""
    title = (f'<b>Security pass</b> · {n} finding{"s" if n != 1 else ""} scored {mn}+{hidden}'
             + (f' · {by}' if by else ""))
    if inline:
        chips = "".join(
            f'<a class="chip sev-{a["severity"]}" data-go-issue="{esc(a["_id"])}" title="{esc(a["text"])}">'
            f'<b>{FINDING_LABEL.get(a["category"], "Security")} {esc(a["score"])}</b> {esc(a["_id"])} '
            f'<span>{esc(os.path.basename(a.get("file") or ""))}:{esc(a.get("line") or "")}</span></a>' for a in sec["shown"])
        body = f'<div class="chips">{chips}</div>' if chips else ""
    else:
        body = "".join(f'<div class="secrow"><span class="mono">{esc(a.get("file"))}</span>{ann_html(a, "issue")}</div>'
                       for a in sec["shown"])
    if not n:
        body = '<div class="muted">Nothing at or above the threshold.</div>'
    return f'<div class="secbox">{title}{body}</div>'


def group_nav(state, g):
    """The bar at the top of a group page: previous/next group, progress, and a list of all groups."""
    groups = state["groups"]; i = groups.index(g)

    def link(x, text):
        if os.path.exists(group_file(x, ".html")) or x is g:
            return f'<a href="{x["id"]}.html">{text}</a>'
        return f'<span class="dim" title="not reviewed yet">{text}</span>'
    prev = link(groups[i - 1], f'← {groups[i - 1]["n"]} · {esc(groups[i - 1]["name"])}') if i > 0 else ""
    nxt = link(groups[i + 1], f'{groups[i + 1]["n"]} · {esc(groups[i + 1]["name"])} →') if i + 1 < len(groups) else ""
    to_review = review_groups(state)
    done = sum(1 for x in to_review if has_review(x))
    options = []
    for x in groups:
        ready = os.path.exists(group_file(x, ".html")) or x is g
        state_words = [w for w, on in (("reviewed", has_review(x) and x["kind"] == "review"),
                                       ("security checked", has_security(x))) if on]
        label = (f'{x["n"]} · {x["name"]} ({x["files"]} files, +{x["add"]} −{x["del"]})'
                 + (f' · {", ".join(state_words)}' if state_words else ""))
        options.append(f'<option value="{x["id"]}.html"{" selected" if x is g else ""}{"" if ready else " disabled"}>'
                       f'{esc(label)}</option>')
    return (f'<div class="gnav">Group <b>{g["n"]} / {len(groups)}</b> · <b>{esc(g["name"])}</b>'
            f'<span>{g["files"]} files · +{g["add"]} −{g["del"]}</span>{prev}{nxt}'
            f'<span>{done}/{len(to_review)} reviewed</span>'
            f'<select onchange="location.href=this.value">{"".join(options)}</select></div>')


def mechanical_section(g, sec=None, heading=True):
    """Lockfiles, generated files and whitespace-only changes: a plain list, no code."""
    rows = "".join(f'<tr><td class="mono">{esc(p)}</td><td>{esc(r)}</td><td>+{a}</td><td>−{d}</td></tr>'
                   for p, a, d, r in sorted(g["list"], key=lambda x: (x[3], x[0])))
    reasons = {}
    for _p, _a, _d, r in g["list"]:
        reasons[r] = reasons.get(r, 0) + 1
    summary = " · ".join(f"{n} {r}" for r, n in sorted(reasons.items(), key=lambda kv: -kv[1]))
    top = (f'<div class="sh"><span class="tb mechtb">Mechanical</span><h2>Not reviewed: {g["files"]} file{"s" if g["files"] != 1 else ""}</h2>'
           f'<span class="cnt">{esc(summary)}</span></div>') if heading else ""
    return (f'<section class="sec mech-sec">{top}'
            + (sec_box(sec, inline=False) if sec is not None else "")
            + f'<table class="mech"><tr><th>File</th><th>Why it is here</th><th>+</th><th>−</th></tr>{rows}</table></section>')


def mechanical_page(state, g, sec=None):
    """Own page for the mechanical group of a big PR."""
    head = (group_nav(state, g) + '<header><div class="tl"><h1>Mechanical changes</h1>'
            f'<span class="meta">{g["files"]} files</span></div>'
            '<div class="ann note flat"><span class="at">Not reviewed by AI. '
            'Skim for anything that does not belong here, e.g. a new package in a lockfile.</span></div></header>')
    return (page_template().replace("%TITLE%", "Mechanical changes").replace("%NAVF%", "").replace("%NAVS%", "")
            .replace("%HEAD%", head).replace("%BYFILE%", mechanical_section(g, sec, heading=False))
            .replace("%BYSTORY%", "").replace("%KEY%", json.dumps("sane-diff:mechanical")))
