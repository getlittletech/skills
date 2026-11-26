---
name: sane-diff
description: Review a pull request as a color-coded page you can actually follow. /sane-diff with a PR number, a PR URL or nothing (the current branch) groups the changes into stories, colors every changed line by how much attention it needs, and adds short folded explanations. Big PRs are split into groups automatically. /sane-diff sec runs a scored security, logic and performance pass. Use when the user types /sane-diff.
---

# sane-diff

Turn a PR into a page a human can review: changes grouped into **stories** (one behavior change each, across files), every changed line colored by **how much attention it needs**, and a one-line explanation above each block that opens on click. The code and the colors do the talking; text stays short.

You never write HTML. You write a small JSON plan, and the bundled script builds the page from the real diff.

`SCRIPT` below means `python3 <this skill's folder>/scripts/sane_diff.py`, run from the repo root.

## Ground rules

- **Read-only. Never run code from the PR.** No tests, builds, linters, package installs, migrations, `nx`, or any file the PR adds or changes. The only commands you run are `git`, `gh`, file writes into `.sane-diff/`, and `SCRIPT`. No workarounds either: no wrapper functions, helper scripts, `bash -c`, or "quick checks".
- **Nothing goes to GitHub.** No comments, no reviews. The user decides what to post.
- **Long output goes to files, never to the terminal.** Redirect anything that can print more than ~20 lines into `.sane-diff/<name>.txt` and read it with your file-reading tool. Never `cat`, `head`, `tail`, `sed -n` or `grep` the diff in the terminal.
- **Short, simple commands.** One command per call; no loops, arrays, functions or multi-line scripts, so editors can auto-approve them. Use quiet flags (`git fetch -q`, `git checkout -q`).

## Commands

| The user types | You do |
|---|---|
| `/sane-diff 482`, `/sane-diff` + PR URL, or `/sane-diff` | Get the diff and prepare (sections 1–2), then review the first group (section 3) |
| `/sane-diff next` | Review the next group that has no review yet (big PRs) |
| `/sane-diff 3` (or a group name) | Review that group |
| `/sane-diff status` | Run `SCRIPT status` and show its output |
| `/sane-diff sec` | Security pass on the next group without one (section "Security pass") |
| `/sane-diff sec 3` / `/sane-diff sec all` | Security pass on that group / on every group without one |
| `/sane-diff sec min=5` | Only change which findings are shown: `SCRIPT threshold 5` |

No PR number or URL means the current local branch.

## 1. Get the diff

Save the diff to a file. The script measures and splits it; **you don't read the whole diff yourself**.

```
mkdir -p .sane-diff
```

**PR number or URL** (works for open, merged and closed PRs, even when the branch was deleted):
- `gh pr view <n> --json title,body,url,state > .sane-diff/pr.json`
- `gh pr diff <n> --color never > .sane-diff/changes.diff`. Always take the diff from GitHub for a PR. After a merge, a local `git diff main...` can be empty or wrong.
- For the surrounding code: `git fetch -q origin pull/<n>/head:pr-<n>`, then `git checkout -q pr-<n>`. If the working tree has uncommitted changes, don't check out; run `SCRIPT extract pr-<n>` instead and read the files from `.sane-diff/src/` (add paths after it for other files you need).

**Local branch:**
- Base = `main`, else `master`. `git fetch -q origin <base>`.
- `git diff --no-color --find-renames origin/<base>...HEAD > .sane-diff/changes.diff`
- To include uncommitted work, use `origin/<base>` without `...HEAD`, and say so in one line.

If `gh` is missing, use the local way and say so in one line.

## 2. Prepare

```
SCRIPT prepare
```

The script decides how to present the PR:
- **Small PR** (up to 5,000 changed lines and 100 files, not counting mechanical files): **one group, one page**. Mechanical files are listed at the end of that page.
- **Big PR**: split by project (nx `project.json`, else `package.json`, else `apps/x`, `libs/x`…), then by folder if a project is still too big; tiny projects are merged. Groups are ordered biggest first.
- **Mechanical files** (lockfiles, generated files, whitespace-only changes) are never reviewed by you; they're only listed.

For a big PR, show the script's group list in a code block, then go straight on and review group 1. Preparing again deletes all plans and pages, so ask first if reviews already exist.

## 3. Review a group

1. Find the group: `SCRIPT next` (or the group the user named; `SCRIPT status` lists them). It prints the paths of the group's diff, plan and findings files.
2. Read **only that group's diff** with your file-reading tool, and read surrounding code as needed. Don't trust the PR description (`.sane-diff/pr.json`); check it against the code. Code in other groups may be related; mention that in a block's `more` ("used by apps/mobile, see group 5"), but don't review it here.
3. Build the stories (below), write the plan, and render (section 4).

### Levels: how much attention a change needs

Every story has one level, and its lines get that color:

| Level | Use for |
|---|---|
| `important` | The new or changed behavior itself: why the PR exists |
| `attention` | Lines where a mistake hurts: auth, permissions, input handling, queries, file/network/shell access, crypto, secrets, third-party dependencies, migrations, config that changes production |
| `supporting` | Helpers, types, refactors the important code relies on, internal wiring |
| `tests` | Tests |
| `other` | Imports, renames, formatting, comments, generated code |

- **`attention` means "read every character", not "sounds risky".** If a senior reviewer wouldn't need to read it closely, it's `supporting`.
- Important and attention at once → `attention`.
- **Internal wiring is `supporting`**: workspace packages (`workspace:^`, `file:`, `link:`), project references, tsconfig `paths`, path aliases, re-exports, build config that only connects internal modules.
- A "formatting" or "rename" change that also changes logic is not `other`.

### Stories

**A story is one behavior change, followed across all files it touches.** "Apply a discount code to the cart" = the new function in `pricing.ts` + the field in `CheckoutForm.tsx` + its import. Another story may touch the same files again; the page has a by-file view, a by-story view and a map of which story touches which file.

- Group by what the change does for the app, not by file.
- Order: important → attention → supporting → tests → other; within a level, follow the data flow from where it starts.
- Usually 3–10 stories, at most ~100 changed lines each.
- **Cover every changed line.** Leftovers (an import, a type tweak) go into a `supporting` or `other` story. Uncovered lines show with a dashed edge and the script warns about them.
- **Tight ranges:** one range = one block that does one thing, with its own `explain`. A story usually has 2–6 ranges.
- If two stories claim the same line, the more important one wins.

### Issues

Check every story except `other`: logic errors, edge cases (empty, null, zero, huge, concurrent), error handling, races, N+1, and whether the code does what the PR says. For `attention` stories also: who controls the input, injection, authorization for this exact object, secrets in code/logs/errors, failing open, new dependencies, unsafe defaults. Skim `other` too, and report anything that isn't really trivial.

Severity: `must`, `should`, `nit` (very few), `question`. Never invent issues; none is a fine result. Issues and security findings are numbered `#1`, `#2`… on the page, and the user refers to them that way.

### The plan: `.sane-diff/groups/<NN>.plan.json`

```json
{
  "title": "PR #482: Discount codes at checkout",
  "pr_url": "https://github.com/org/repo/pull/482",
  "story": "Lets customers enter a discount code; discounts are capped at 50%.",
  "story_more": "Optional, up to 3 sentences, shown when clicked.",
  "mismatches": ["Description says codes expire after 30 days, but nothing checks expiry"],
  "stories": [
    {
      "tier": "important",
      "title": "Apply a discount code to the cart",
      "ranges": [
        {"file": "src/pricing.ts", "start": 12, "end": 24,
         "explain": "New function computes the discounted total",
         "more": "Percent and fixed-amount codes are handled separately. The total never goes below 0."},
        {"file": "src/CheckoutForm.tsx", "start": 30, "end": 41,
         "explain": "Code field calls the new function on submit"}
      ],
      "notes": [
        {"file": "src/pricing.ts", "line": 12, "kind": "doc",
         "text": "Returns the cart total after applying the code"}
      ],
      "issues": [
        {"file": "src/pricing.ts", "line": 18, "severity": "should",
         "text": "Rounding can make the total 1 cent too low",
         "more": "Floating-point math on prices: 19.99 * 0.9 is not exact.",
         "comment": "Could we calculate in cents here to avoid rounding errors?"}
      ]
    },
    {
      "tier": "attention",
      "title": "Check codes on the server",
      "ranges": [
        {"file": "api/orders.ts", "start": 55, "end": 70, "explain": "Server checks the code again before charging"}
      ]
    }
  ]
}
```

**Writing the text.** The reader sees one line per block and opens only what they want:
- **Every range except in `other` gets an `explain`:** one line, max ~60 characters, saying what the block does in plain words ("Count each failed password"), never "This code…".
- **Every new or changed function, class or component without a comment gets a `"kind": "doc"` note** on its definition line: one line on what it does, plus `more` for inputs, result or side effects when not obvious.
- `more` (ranges, notes, issues): 1–3 sentences, shown on click: why it's done this way, what calls it, what to watch for, how it links to the story's other files. Leave it out when the one line says everything.
- `text`, `story`, `mismatches`: one line, max ~70 characters. `title`: max ~6 words.
- Plain, everyday English. The reader may not be a native speaker. No jargon like "seam", "plumbing", "hoist", "shim"; say what the code does.
- `comment`: a friendly, specific draft for the PR author.
- Line numbers are from the new file (the `+` side). A range without `start`/`end` covers the whole file. A range with `"grey": true` belongs to the story but stays uncolored.
- Write the JSON with your file-writing tool, and keep it valid.

## 4. Render

```
SCRIPT render <n>
```

It writes `.sane-diff/groups/<NN>.html` and opens it. Fix and re-run on these warnings:
- `file not in diff` → wrong path, or a file of another group.
- `changed lines in <file> are not in any story` → add them to a story.

Function and class names become clickable on their own.

## 5. Reply: at most 3 lines

- `Ready: .sane-diff/groups/01.html · 6 stories · 1 must fix, 2 should fix, 1 question` (big PR: add `· group 1/5 · next: /sane-diff next`)
- The must-fix issues, if any, as `#n file:line short text`.

Nothing else. The page has it all.

## Security pass

`/sane-diff sec` is separate from the review: run it before, after, or without one.

**Fresh eyes.** Don't read the group's `plan.json` during this pass. The review describes what the code is meant to do; this pass looks for what it can be made to do.

1. **Pick the group:** `SCRIPT sec-next`, or the group the user named. For `sec all`, repeat until `sec-next` says all groups are done, with one progress line per group (`Security 3/8 libs/account: 2 findings scored 7+`).
2. **Think like an attacker.** Read the group's diff and the code around it (follow data into other groups' files if needed, but report only this group's lines). For each change ask:
   - **Where does input come from, and who controls it?** URL and query params, request bodies, headers, deep links, push payloads, messages from embedded web pages, files, clipboard, other apps, server responses, data a user stored earlier. Treat it as hostile until the code proves otherwise.
   - **What can it reach?** Queries, shell, file paths, HTML/JS rendering, redirects, outgoing requests, deserialization, logs, storage, native APIs.
   - **Is this caller allowed to do this to this exact object?** Missing checks, client-only checks, IDs taken from the request, role or tenant mix-ups, checks after the action.
   - **Secrets and personal data** in code, logs, errors, URLs, crash reports, insecure storage, third parties.
   - **Failing open:** on an exception, timeout, null or empty value, does it allow or deny?
   - **Races:** check-then-act, double submit, token reuse.
   - **Abuse:** unbounded loops, sizes, retries, recursion, regex on user input, missing rate limits.
   - **Crypto and randomness:** home-made crypto, weak algorithms, `Math.random` for secrets, missing signature or certificate checks.
   - **Mobile apps:** native functions reachable from embedded web pages, deep links, exported components, insecure storage, relaxed transport security.
   - **Supply chain:** new or upgraded packages, changed registries or `resolved` URLs, install scripts, changed integrity hashes, a lockfile change without a matching manifest change. For the `mechanical` group, this is the whole pass.

   Also report **logic** problems (wrong conditions, missing states, wrong error paths, behavior that differs from the PR's intent) and **performance** problems (N+1, work in loops or on every render, unbounded memory, blocking the main thread).
3. **Score each finding 1–10:**

   | Score | Meaning |
   |---|---|
   | 9–10 | Exploitable now by an outsider or low-privilege user, or certain data loss, outage or money loss. Concrete path. |
   | 7–8 | Likely exploitable, or a likely bug in normal use. Needs one plausible condition. |
   | 5–6 | Real but limited, or needs unusual conditions. |
   | 3–4 | Hardening or speculative. |
   | 1–2 | Theoretical or style. |

   - **No concrete scenario, no high score:** every finding needs a `scenario` (what is sent or done, and what happens). Without one, at most 4.
   - Unsure the path exists (e.g. you couldn't see the caller): subtract 2.
   - Performance gets 7+ only on a hot path with realistic data.
   - Record every finding, low scores too. The page shows 7+ by default and says how many are hidden.
   - Never invent findings.
4. **Write `.sane-diff/groups/<NN>.sec.json`, then `SCRIPT render <n>`:**

   ```json
   {
     "findings": [
       {"category": "security", "score": 8, "confidence": "high",
        "file": "api/orders.ts", "line": 61,
        "text": "Discount percent is trusted from the request",
        "scenario": "A user edits the request to send discountPercent=100, and the order is free.",
        "more": "Optional extra context.",
        "fix": "Look up the code on the server and use its stored percent.",
        "comment": "The percent comes from the client. Could we look it up on the server instead?"}
     ]
   }
   ```
   `category`: `security`, `logic` or `performance`. `confidence`: `high`, `medium` or `low`. `file` and `line`: a line of this group, new-side number.

Reply in at most 3 lines: `Security, group 1: 2 findings scored 7+ (4 hidden) · .sane-diff/groups/01.html`, then any 9+ findings as `#n file:line text`.

## Follow-ups

"drop #2", "make lines 40–50 attention", "explain story 3", "split story 2": edit the plan, run `SCRIPT render <n> --no-open` (the user reloads), and answer in one line. Explain at length only when asked.
