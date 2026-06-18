---
name: sw-git-commit
description: Analyze uncommitted changes (staged, unstaged, untracked) and split them into multiple well-scoped Conventional Commits, each representing one logical concern. Use this skill whenever the user asks to commit, make commits, split commits, organize commits, "separar em commits", "faz os commits", "commita isso", "prepara pra commit", or mentions committing in any form — even if they don't explicitly ask for separation. Also trigger proactively when the user finishes implementing something substantial (multiple files, multiple concerns) and is clearly at a commit boundary. Never commits without showing the plan and getting explicit approval first.
---

# Git Commit

Take a working tree full of changes and turn it into a clean, reviewable sequence of commits — one concern per commit, following Conventional Commits, honoring the repo's existing language and conventions.

## Why split commits

A well-split history is the difference between a PR that can be reviewed in 10 minutes and one that can't be reviewed at all. Each commit should answer one question. Mixing a refactor, a feature, and its tests into one commit makes the diff unreadable and makes `git blame` / `git revert` nearly useless later.

The goal of this skill is to do the splitting work *for* the user so they never have to fight `git add -p` again — including hunk-level staging on the user's behalf when a single file mixes concerns (see Rule E and Step 6).

## Rule: every decision is an `AskUserQuestion`

**Every decision you need from the user goes through the `AskUserQuestion` tool (a clickable menu) — never as loose text asking them to type, and NEVER end a turn with a plain-text question.** This applies to every decision point in this skill:

- **Plan approval** (Step 5) — present **Approve / Edit / Cancel** as menu options, not a typed `yes/edit/cancel`.
- **Entangled hunks** (Rule E) — when one file's concerns can't be cleanly separated: **Keep in one commit / Split manually**.
- **Subject language** when history is too sparse to detect it — offer the likely languages as options.
- **Any confirmation before a destructive or irreversible step.**

For open-ended answers, offer the most likely options and rely on the menu's **"Other"** field for free input. You can bundle up to 4 questions in one call.

**The one exception:** free-form *plan edits*. When the user picks **Edit**, they describe the change in their own words ("merge 2 and 3", "make commit 2 a fix") — that's them driving, not you asking, so don't force a menu there.

Don't ask what you can safely infer from the repo/diff — just proceed and state the assumption.

## Workflow

1. **Scan the working tree** — collect staged, unstaged, and untracked changes
2. **Detect repo conventions** — read the last ~20 commits to learn the language, commit-type vocabulary, and scope style already in use
3. **Group changes into logical commits** — apply the splitting rules below
4. **Build a commit plan** — ordered list of commits with files + message for each
5. **Show the plan to the user and wait for approval** — never commit without explicit OK
6. **Execute commits sequentially** — stage the files for each commit, commit, move to the next

### Step 1 — Scan

Run these in the shell to get the full picture (git runs via the shell — there's no dedicated non-shell tool for it; for reading file *contents*, prefer the dedicated file-read tool over `cat`):

```
git status --porcelain
git diff              # unstaged
git diff --staged     # staged
```

For untracked files, also read their content so you know what you're grouping.

If `git status` returns empty, tell the user there's nothing to commit and stop.

### Step 2 — Detect conventions

Read the last ~20 commits:

```
git log --oneline -20
git log -5              # full messages for body style
```

Extract:
- **Subject language** — Portuguese? English? Spanish? Use whichever dominates the log. This becomes the subject language.
- **Type vocabulary** — what types appear (`feat`, `fix`, `refactor`, `test`, `perf`, `chore`, `docs`, `ui`, `ux`, `build`, `ci`, `style`, `revert`, etc.). Reuse only types the repo actually uses; don't introduce new ones unless there's no alternative.
- **Scope style** — do scopes use `(module)`, `(feature-name)`, `(file)`, or no scope at all? Match what you see.
- **Casing and punctuation** — subjects lowercase? Trailing period or not? Imperative or past tense? Mirror it.
- **Body presence** — do existing commits use bodies? How long? Mirror the norm.

Commit *types* stay in English regardless of the subject language — `feat`, `fix`, etc. are the Conventional Commits standard and the log will almost always use them in English.

**Sparse or empty history** — if the repo has fewer than ~5 commits (or none yet), there's no convention to mirror. Fall back to standard Conventional Commits: lowercase English subjects, imperative mood, no scope unless the change clearly maps to one. If the working tree's content is clearly in another language, ask via `AskUserQuestion` which subject language they want rather than guessing.

### Step 3 — Group changes

Apply these splitting rules. They exist to make each commit independently reviewable and revertable.

**Rule A — Tests go in their own commit, separate from the code they test.**
A test commit that lands alongside its feature commit lets a reviewer check the code first and then verify the tests cover it, without the two diffs tangling. The type is `test(scope):`.

**Rule B — Refactors never mix with features or fixes.**
A refactor changes *how* something works without changing *what* it does. A feature changes *what*. Mixing them hides behavioral changes inside a large diff. If a refactor was necessary to enable a feature, the refactor goes first, the feature second.

**Rule C — Infra, config, and migrations get isolated commits.**
Schema migrations, CI workflow edits, Docker/compose changes, package manifests (`composer.json`, `package.json`, `Cargo.toml`, etc.), environment example files, and editor config all change the *environment* rather than the app. They should land separately so ops/infra reviewers can focus on them. Appropriate types: `build`, `ci`, `chore`, or `feat(db)` for schema additions.

**Rule D — Different scopes become different commits.**
If the changes span two unrelated areas of the codebase (e.g., `auth` and `billing`), they become two commits even if they were implemented in the same session. A commit should be scannable as one concern.

**Rule E — A single file with mixed concerns is split by hunk, not lumped together.**
Whole-file staging is the default, but it fails when one file carries two unrelated changes (e.g., a bug fix and an unrelated refactor in the same module). When that happens, stage the relevant hunks per commit instead of the whole file (see Step 6). If the hunks are too entangled to separate cleanly, don't guess — surface it in the plan and ask via `AskUserQuestion` whether to keep them in one commit or split manually.

### Conflict between rules

When rules conflict, resolve in this order:
1. Infra/config isolation (Rule C) — almost always the outermost split
2. Scope boundaries (Rule D)
3. Refactor vs feature (Rule B)
4. Tests last (Rule A)

So a working tree touching `db/schema.sql`, `src/auth/login.ts`, and `tests/auth/login.test.ts` becomes three commits in order: migration → feature → tests.

### Step 4 — Build the plan

For each commit, decide:
- **Files** included (absolute list)
- **Type** — one of the types already present in the repo's history
- **Scope** — the module, feature, or area name, matching repo style
- **Subject** — imperative, in the detected language, no trailing period, concise (≤70 chars)
- **Body** — only if the change is complex or carries non-obvious context; otherwise omit. A body is worth writing when the *why* would be lost otherwise (workaround for a bug, non-obvious decision, breaking change). Don't write bodies for routine changes — `git diff` already shows the *what*.

Order commits so each leaves the tree in a working state if possible. Infrastructure/migration first, then code, then tests.

### Step 5 — Present the plan

Show the user a clear, numbered plan like this:

```
Found 12 changed files. Proposed split into 4 commits:

1. feat(db): add users.email_verified column
   files:
     + database/migrations/0042_add_email_verified.sql

2. refactor(auth): extract token parsing into helper
   files:
     M src/auth/token.ts
     M src/auth/session.ts

3. feat(auth): require email verification on login
   files:
     M src/auth/login.ts
     M src/auth/errors.ts

4. test(auth): cover email verification flow
   files:
     + tests/auth/login.test.ts
     M tests/auth/helpers.ts

→ approval asked via AskUserQuestion:  [ Approve ]  [ Edit ]  [ Cancel ]
```

Use `+` for new, `M` for modified, `D` for deleted. Keep it scannable — don't dump full diffs.

Then ask for approval with an `AskUserQuestion` menu — **Approve / Edit / Cancel** — never a typed yes/no:
- **Approve** → proceed to Step 6.
- **Edit** → the user describes the change in free text ("change commit 2 to fix instead of refactor", "merge 2 and 3", "split 1 into two"); apply it and re-present the plan with a fresh menu.
- **Cancel** → stop without committing.

Don't commit until the user picks **Approve**.

### Step 6 — Execute

If anything is already staged when you start, the plan reorganizes it — say so, then run `git reset` once to clear the index so each commit contains exactly what you stage (this respects the user's pre-staged intent by reflecting it in the plan, not by silently overriding it). Then, for each commit in order:

1. **Stage exactly this commit's changes:**
   - Whole files: `git add <files for this commit>` — only the files for this commit.
   - Mixed-concern file (Rule E): stage only the relevant hunks with `git add -p <file>` (or `git apply --cached` with a hunk patch); leave the other hunks for their own commit.
2. `git commit -m "<subject>"` — or with a body via heredoc if one is warranted.
3. **Verify before moving on:** confirm the commit captured the intended files (`git show --stat HEAD`) and check `git status`. If a pre-commit hook *reformatted* files (working tree is dirty again after a successful commit), review the change — if it belongs to the commit you just made, `git add` it and `git commit --amend --no-edit`; if it affects later commits, fold it into those.

**Never use `git add .` or `git add -A`.** Stage files (or hunks) explicitly — that's the whole point of splitting.

**`Co-Authored-By` trailer:** follow the repo/environment convention. If the project or harness requires the trailer, include it; if the repo's history never uses it and nothing requires it, omit it. When unsure, ask.

**Never use `--no-verify`.** If a pre-commit hook *fails*, stop and report the failure to the user. Do not attempt to bypass.

If a commit fails mid-plan, stop. Do not continue the remaining commits — the user needs to know the state. Report which commits landed, which failed, and which are still pending.

## Message format reference

### Subject line

```
<type>(<scope>): <subject>
```

- `<type>`: Conventional Commits type in English (`feat`, `fix`, `refactor`, `test`, `perf`, `chore`, `docs`, `build`, `ci`, `style`, `revert`, and any additional types the repo already uses like `ui`, `ux`)
- `<scope>`: the area touched, matching the repo's convention. Omit the parentheses entirely if the repo doesn't use scopes.
- `<subject>`: imperative mood ("add" not "added" or "adds"), lowercase (unless proper nouns), no trailing period, ≤70 chars, in the repo's dominant subject language

### Body (when warranted)

Separate from subject by a blank line. Wrap at ~72 chars. Explain *why*, not *what* — the diff already shows the what.

```
feat(auth): require email verification on login

Compliance team flagged unverified accounts as a GDPR risk after the
Q3 audit. Users with unverified emails can still access the app in
read-only mode, but mutations now return 403.
```

### Breaking changes

Add a `BREAKING CHANGE:` footer (uppercase, with colon) describing the break and the migration path:

```
feat(api): remove deprecated v1 endpoints

BREAKING CHANGE: /api/v1/* now returns 410 Gone. Clients must
migrate to /api/v2/* — see MIGRATION.md for the mapping.
```

## Examples

### Example 1 — Mixed working tree

Changes:
- `src/users/service.ts` (modified)
- `src/users/controller.ts` (modified)
- `tests/users/service.test.ts` (new)
- `package.json` (modified — new dependency added)

Plan:
1. `chore(deps): add bcrypt for password hashing`
2. `feat(users): hash passwords before persistence`
3. `test(users): cover password hashing in service`

### Example 2 — Pure refactor across multiple files

Changes:
- 8 files across `src/payments/` (modified, all renames/extractions)

Plan:
1. `refactor(payments): extract gateway adapter interface`

A single refactor is fine as a single commit if it's genuinely one concern. Don't over-split.

### Example 3 — Feature with enabling refactor

Changes:
- `src/cache.ts` (refactored to support TTL)
- `src/products/list.ts` (uses new cache TTL)
- `tests/products/list.test.ts` (new)

Plan:
1. `refactor(cache): support per-entry TTL`
2. `feat(products): cache product list for 5 minutes`
3. `test(products): cover list cache expiry`

## Edge cases

- **Nothing to commit**: stop immediately, tell the user.
- **Only one logical concern**: don't force a split. A single commit is fine if the change is genuinely atomic. The rules are about separating *different* concerns, not about producing many commits.
- **Secrets detected** in the diff (API keys, passwords, `.env` files with real values): stop and warn the user before committing anything.
- **Merge conflict markers** in the diff (`<<<<<<<`, `=======`, `>>>>>>>`): stop and warn — the user hasn't finished resolving the merge.
- **Binary files** (images, compiled artifacts): include them in the most topically related commit. Don't try to `git diff` them.
- **Generated files** (lockfiles, build output): usually belong with the commit that caused them. A `package-lock.json` change goes with the `package.json` change that triggered it.
- **Pre-commit hook fails**: stop. Do not bypass with `--no-verify`. Report the failure and let the user fix it.
- **User wants to undo a commit after it landed**: that's outside the scope of this skill — direct them to `git reset --soft HEAD~N` manually.

## What this skill does NOT do

- Push commits to a remote (leave that to the user)
- Create branches
- Open pull requests
- Amend or rewrite existing commits
- Stash changes

Keep the scope tight: split working-tree changes into commits, nothing more.
