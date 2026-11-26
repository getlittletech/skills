---
name: sane-steps
description: Write code with AI one small step at a time. /sane-steps plan followed by a task makes a numbered plan; /sane-steps next does exactly one step (usually one file, at most ~100 changed lines) and then stops, so the developer can read the code and give feedback before the next step. Use when the user types /sane-steps.
---

# sane-steps

Turn-based coding: you make one move, then it's the developer's turn. They read the code, ask, or ask for changes, and only then say `next`.

The goal is that the developer **understands every line** that goes in. Speed comes second. Small steps, a short explanation, then stop.

## Commands

| User types | You do |
|---|---|
| `/sane-steps plan <what to build>` | Make a plan (section "Plan"). Write no code. |
| `/sane-steps next` | Do the next unchecked step (section "Next"), then stop. |

Anything else the user writes between steps ("rename that", "why this?", "use a map instead") is feedback on the step you just did: answer it or change that step's code, then stop again. Do not start the next step until they say `next`.

## The plan file

The plan lives in `.sane-steps/plan.md` in the repo root, so it survives new chat sessions and the developer can edit it by hand. Always read it before acting, and treat the developer's edits as the truth.

```markdown
# Add discount codes to checkout

Goal: customers can enter a code at checkout; percent and fixed codes; max 50% off.

- [ ] 1. Discount types and validation
  - Files: src/pricing/discount.ts (new)
  - Why: one place that knows what a valid code is, before any UI uses it
  - Check: `npx vitest src/pricing/discount.test.ts` passes, or read the 3 rules in the file
- [ ] 2. Apply a code to the cart total
  - Files: src/pricing/cart.ts
  - Why: …
  - Check: …
```

Each step has:
- a short **title** saying what changes for the app, in plain words,
- the **files** it touches (usually one, at most three),
- **why** it comes at this point, in one line,
- a **check**: how the developer can see it works (a test, a command, something to click, or what to read).

## Plan

1. Read the code that the task touches, enough to know where things go. Ask at most one or two questions if something important is truly unclear; otherwise make sensible choices and write them in the plan's goal.
2. Split the work into steps:
   - **Each step leaves the code working.** It builds and the existing tests still pass. No half-finished states between steps.
   - **Small:** usually one file, at most ~100 changed lines. Split anything bigger.
   - **Order:** foundations first (types, data, pure logic), then the code that uses them, then UI, then cleanup. Tests go with the step they test, or right after it.
   - Usually 4–12 steps. A tiny task may have 2.
3. Write `.sane-steps/plan.md`. If a plan already exists and has unchecked steps, ask before replacing it.
4. In chat: the numbered step titles, one line each, and `Type /sane-steps next to start.` Then stop.

## Next

1. Read `.sane-steps/plan.md` and take the first unchecked step. If all are done, say so in one line and suggest a final look at the whole change (e.g. `git diff`).
2. Do **only that step**. Do not touch files outside it unless it can't work otherwise; if you have to, say so.
3. Write code a human can follow: clear names, small functions, a short comment only where the *why* isn't obvious.
4. If the step has a quick check (one test file, a type check of the changed file), you may run it once. Don't run long builds or the whole test suite.
5. Tick the step in the plan file (`- [x]`).
6. Reply in this shape, and keep it short:

```
Step 2/7 done: Apply a code to the cart total

Changed: src/pricing/cart.ts (+38 −4)

Look at:
- cart.ts:41 applyDiscount: percent codes are capped at 50% here
- cart.ts:58 the total never goes below 0
- cart.ts:12 new import of validateCode from step 1

Why this way: the cap lives next to the calculation, so the UI can't bypass it.
Check: npx vitest src/pricing/cart.test.ts ✓ (passed)

Next: 3. Show the code field at checkout. Type /sane-steps next.
```

   - **Look at:** 2–5 bullets, each with `file:line` and what to notice there. Point at decisions, not at every line.
   - **Why this way:** one or two sentences, only if there was a real choice.
   - Don't paste the code into the chat. The developer reads it in the editor.
7. **Stop.** Even if the next step looks tiny or obvious. The pause is the point.

## When the plan turns out wrong

If a step shows the plan doesn't work (a missing piece, a better order, a wrong assumption), don't quietly do something else. Say in one or two lines what you found, then stop and let the developer decide.

## Rules

- **One step per `next`. Always stop.** Never continue into the next step on your own.
- **Never commit, push or open a PR** unless the developer asks.
- **Plain, simple English** in the plan and in chat. The reader may not be a native speaker. No jargon where a normal word works.
- **No surprises:** no new dependencies, no renames or refactors of unrelated code, no formatting of whole files, unless the step says so.
- **Keep the plan file current.** If the developer changes the code themselves between steps, read it again and build on their version.
