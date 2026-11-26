#!/usr/bin/env python3
"""sane-diff: turn a PR diff into a color-coded review page.

Run from the repository root. Python 3, standard library only.

  sane_diff.py prepare [--diff FILE]   read .sane-diff/changes.diff and decide the groups
                                       (small PR: one group, one page; big PR: several groups)
  sane_diff.py next                    the next group to review
  sane_diff.py render N [--min S]      build the page for group N from its plan and/or findings
  sane_diff.py status                  all groups, and which are reviewed / security-checked
  sane_diff.py sec-next                the next group without a security pass
  sane_diff.py threshold S             show security findings scored S or more, on all pages
  sane_diff.py extract REF [PATH ...]  save files as they are at git REF into .sane-diff/src/
"""
import argparse
import json
import os
import subprocess
import sys
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sane.core import DEFAULT_MIN_SCORE  # noqa: E402
from sane.diffparse import parse  # noqa: E402
from sane.groups import (MAX_FILES, MAX_LINES, STATE_DIR, find_group, group_file, has_review,  # noqa: E402
                         has_security, load_findings, load_state, mechanical_group, next_to_review,
                         next_without_security, print_groups, review_groups, save_state, split)
from sane.render import group_nav, mechanical_page, mechanical_section, render_page  # noqa: E402


# ---------------------------------------------------------------- pages

def render_group(state, g, quiet=False):
    """Write the page for one group. Returns its path, or None if there is nothing to show yet."""
    min_score = state.get("min_score", DEFAULT_MIN_SCORE)
    mechanical = mechanical_group(state)

    if g["kind"] == "mechanical":
        if state["single"]:  # small PR: the mechanical list lives inside the one review page
            main = review_groups(state)
            return render_group(state, main[0], quiet) if main else None
        page, warnings, stories = mechanical_page(state, g, load_findings(g, min_score)), [], 0
    else:
        plan_file = group_file(g, ".plan.json")
        findings = load_findings(g, min_score)
        if os.path.exists(plan_file):
            plan = json.load(open(plan_file, encoding="utf-8"))
        elif findings is not None:
            plan = {"title": f'{g["name"]} (security pass only, not reviewed yet)', "stories": []}
        else:
            if quiet:
                return None
            sys.exit(f"Missing {plan_file}. Write the plan for group {g['n']} first.")
        extra = ""
        if state["single"] and mechanical:
            extra = mechanical_section(mechanical, load_findings(mechanical, min_score))
        nav = "" if state["single"] else group_nav(state, g)
        files = parse(open(group_file(g, ".diff"), encoding="utf-8", errors="replace").read())
        page, warnings = render_page(files, plan, nav, f'{g["id"]}:', findings, extra)
        stories = len(plan.get("stories") or [])

    out = group_file(g, ".html")
    open(out, "w", encoding="utf-8").write(page)
    if not quiet:
        note = ""
        if findings_summary := load_findings(g, min_score):
            note = f', security: {len(findings_summary["shown"])} shown (score {findings_summary["min"]}+), ' \
                   f'{findings_summary["hidden"]} hidden'
        print(f"Wrote {out}: group {g['n']} · {g['name']} · {g['files']} files, {stories} stories{note}")
        for w in warnings:
            print("WARNING:", w)
    return out


def refresh_other_pages(state, current):
    """Re-render pages that exist, so their group bar shows the latest progress."""
    if state["single"]:
        return
    for g in state["groups"]:
        if g is not current and (g["kind"] == "mechanical" or has_review(g) or has_security(g)):
            render_group(state, g, quiet=True)


def describe(g, label="Next"):
    print(f"{label}: group {g['n']} · {g['name']} · {g['files']} files · +{g['add']} −{g['del']}")
    print(f"  diff:     {group_file(g, '.diff')}")
    print(f"  plan:     {group_file(g, '.plan.json')}")
    print(f"  findings: {group_file(g, '.sec.json')}")


# ---------------------------------------------------------------- commands

def cmd_prepare(args):
    state = split(args.diff)
    files = sum(g["files"] for g in state["groups"])
    if state["single"]:
        print(f"Small PR ({files} files): one page, no groups.")
        if state["groups"] and state["groups"][0]["kind"] == "review":
            describe(state["groups"][0], "Review")
        mech = mechanical_group(state)
        if mech:
            print(f"  + {mech['files']} mechanical file{'s' if mech['files'] != 1 else ''} (lockfiles, generated, whitespace), listed at the end of the page")
    else:
        print_groups(state, f"Big PR ({files} files, over {MAX_LINES} changed lines or {MAX_FILES} files): "
                            f"{len(state['groups'])} groups.")
        mech = mechanical_group(state)
        if mech:
            render_group(state, mech, quiet=True)
        first = next_to_review(state)
        if first:
            describe(first, "Start with")


def cmd_next(args):
    g = next_to_review(load_state())
    describe(g) if g else print("All groups are reviewed.")


def cmd_render(args):
    state = load_state()
    if args.min is not None:
        state["min_score"] = args.min
        save_state(state)
    g = find_group(state, args.group)
    out = render_group(state, g)
    refresh_other_pages(state, g)
    if out and not args.no_open:
        webbrowser.open("file://" + os.path.abspath(out))


def cmd_status(args):
    print_groups(load_state())


def cmd_sec_next(args):
    state = load_state()
    g = next_without_security(state)
    if not g:
        print("All groups have a security pass.")
        return
    describe(g, "Next for security")
    if g["kind"] == "mechanical":
        print("  (mechanical group: check lockfiles and dependency changes)")


def cmd_threshold(args):
    state = load_state()
    state["min_score"] = args.score
    save_state(state)
    count = 0
    for g in state["groups"]:
        if g["kind"] == "mechanical" and state["single"]:
            continue
        if (g["kind"] == "mechanical" or has_review(g) or has_security(g)) and render_group(state, g, quiet=True):
            count += 1
    print(f"Showing security findings scored {args.score:g} or more. Re-rendered {count} page(s).")


def cmd_extract(args):
    root = os.path.join(STATE_DIR, "src")
    paths = list(args.paths)
    if not paths:
        diff = os.path.join(STATE_DIR, "changes.diff")
        if not os.path.exists(diff):
            sys.exit(f"No paths given and {diff} not found.")
        text = open(diff, encoding="utf-8", errors="replace").read()
        paths = [f["new"] for f in parse(text) if f["status"] != "deleted" and not f["binary"]]
    saved, missing = 0, 0
    for path in paths:
        result = subprocess.run(["git", "show", f"{args.ref}:{path}"], capture_output=True)
        if result.returncode:
            print(f"missing {path}")
            missing += 1
            continue
        target = os.path.join(root, path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        open(target, "wb").write(result.stdout)
        saved += 1
    print(f"Saved {saved} files to {root}/" + (f", {missing} missing" if missing else ""))


def main():
    parser = argparse.ArgumentParser(description="Color-coded, step-by-step PR review pages.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare", help="decide the groups for .sane-diff/changes.diff")
    p.add_argument("--diff", default=os.path.join(STATE_DIR, "changes.diff"))
    p.set_defaults(run=cmd_prepare)

    sub.add_parser("next", help="the next group to review").set_defaults(run=cmd_next)

    p = sub.add_parser("render", help="build the page for a group")
    p.add_argument("group", help="number, group-N, or name")
    p.add_argument("--min", type=float, help="show security findings scored at least this (default 7)")
    p.add_argument("--no-open", action="store_true", help="don't open the page in the browser")
    p.set_defaults(run=cmd_render)

    sub.add_parser("status", help="all groups and their progress").set_defaults(run=cmd_status)
    sub.add_parser("sec-next", help="the next group without a security pass").set_defaults(run=cmd_sec_next)

    p = sub.add_parser("threshold", help="change the minimum score of shown security findings")
    p.add_argument("score", type=float)
    p.set_defaults(run=cmd_threshold)

    p = sub.add_parser("extract", help="save files at a git ref into .sane-diff/src/")
    p.add_argument("ref")
    p.add_argument("paths", nargs="*")
    p.set_defaults(run=cmd_extract)

    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
