# Sane skills

Agent skills that make coding with AI fun again. Get your sanity back.

## Skills

- **sane-steps**: write code with AI one small step at a time.
  `/sane-steps plan <task>` makes a plan. `/sane-steps next` does one step, then stops,
  so you can read the code and give feedback before the next one.

- **sane-diff**: review a pull request with a diff you can actually follow.
  `/sane-diff 482` (or a PR URL, or nothing for the current branch) builds a review page:
  - changes grouped into **stories**, one behavior change each, across files
  - every changed line **colored by how much attention it needs**:
    important, attention, supporting, tests, other
  - a **one-line explanation** above each block, with more on click
  - a **map** of which story touches which file, and by-file and by-story views
  - **big PRs** are split into groups automatically; `/sane-diff next` reviews the next one

  `/sane-diff sec` adds a separate security, logic and performance pass.
  Each finding gets a score, and only the serious ones are shown.

  sane-diff only reads the PR: it never runs its code and never posts to GitHub.
  It needs `git`, Python 3, and the GitHub CLI (`gh`) for PRs.

## Install

Copy the skill folders into your agent's skills folder, for example:

    ~/.agents/skills/sane-steps/SKILL.md
    ~/.agents/skills/sane-diff/SKILL.md

Copy the whole `sane-diff` folder, including its `scripts` folder.

## License

MIT