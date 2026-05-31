# CLAUDE.md

This file documents the repository structure, development workflows, and conventions for AI assistants (Claude Code and similar tools) working in this codebase.

---

## Repository Overview

**Repository:** `tskoopy-droid/claude-code-respository`
**Purpose:** This repository is being initialized. Update this section as the project takes shape.

> Note: "claude-code-respository" contains a typo in the repo name ("respository" vs "repository"). This is the canonical name — do not attempt to rename it.

---

## Repository Structure

This repository is currently empty. As files are added, document the structure here. Example template:

```
/
├── CLAUDE.md          # This file — AI assistant guidance
├── README.md          # Human-facing project overview
├── src/               # Source code
├── tests/             # Test suite
├── docs/              # Documentation
└── .github/
    └── workflows/     # CI/CD pipelines
```

---

## Branch Strategy

| Branch pattern | Purpose |
|---|---|
| `main` | Production-ready, protected |
| `claude/<feature>-<id>` | AI-driven feature work (e.g. `claude/claude-md-docs-YjdcM`) |
| `feat/<name>` | Human-driven feature branches |
| `fix/<name>` | Bug fixes |
| `chore/<name>` | Maintenance, dependency updates |

**Rules:**
- Never push directly to `main`.
- All work lands via pull request.
- Branch names are lowercase with hyphens, no underscores.
- Claude Code sessions develop on the branch designated in the session context; never push to a different branch without explicit permission.

---

## Git Conventions

### Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short imperative summary>

[optional body]

[optional footer]
```

**Types:** `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `perf`

**Examples:**
```
feat(auth): add JWT refresh token support
fix(api): handle null response from upstream service
docs: add CLAUDE.md with development conventions
chore(deps): bump lodash from 4.17.20 to 4.17.21
```

- Summary line ≤ 72 characters, imperative mood ("add" not "added").
- Body explains *why*, not *what* — the diff already shows what changed.
- Never skip pre-commit hooks (`--no-verify`).

### Staging files

Prefer `git add <specific-file>` over `git add .` or `git add -A` to avoid accidentally staging secrets or build artifacts.

---

## Development Workflow

### Starting work

```bash
git fetch origin
git checkout -b feat/<name> origin/main
```

### Running checks (update once tooling is set up)

```bash
# Replace with actual commands once the project is configured
npm test        # or: pytest, go test ./..., cargo test, etc.
npm run lint    # or: ruff check ., eslint ., etc.
npm run build   # verify build passes before pushing
```

### Pushing

```bash
git push -u origin <branch-name>
```

On network failure, retry with exponential backoff: wait 2 s, 4 s, 8 s, 16 s between attempts.

### Pull requests

- Keep PRs focused — one logical change per PR.
- PR title follows the same Conventional Commits format as commit messages.
- Include a short summary and a test plan in the PR description.
- Do not merge your own PR without a review (exception: trivial docs/chore work in an empty repo bootstrapping phase).

---

## Working with Claude Code

### Session model

Each Claude Code web session runs in an isolated, ephemeral container. The repository is cloned fresh at session start. Any work that needs to persist **must be committed and pushed** before the session ends.

### Designated branches

The active development branch for each session is specified in the session's system context. Always develop on that branch. Never push to `main` or another branch without explicit user instruction.

### What Claude Code will do autonomously

- Read, edit, and create files within the repository.
- Run tests, linters, and build commands.
- Commit changes with descriptive messages.
- Push to the designated branch.
- Open pull requests **only when explicitly asked**.

### What Claude Code will confirm before doing

- Destructive git operations (reset, force-push, branch deletion).
- Actions visible to others (commenting on issues/PRs, sending notifications).
- Pushing to `main` or any undesignated branch.
- Any action outside the repository (external API calls, infrastructure changes).

### Tool use preferences

- Use `Read`, `Edit`, `Write` tools over shell `cat`/`sed`/`echo`.
- Prefer targeted `git add <file>` over `git add .`.
- For broad codebase exploration, spawn an `Explore` subagent rather than running many sequential greps.

---

## Code Conventions

Document language/framework-specific conventions here as the codebase grows. Examples:

### General

- No commented-out code left in commits.
- No `console.log` / `print` / `fmt.Println` debug statements in committed code.
- No TODO comments without an associated issue number.
- Secrets and credentials never committed — use environment variables or a secrets manager.

### Naming

- Files: `kebab-case` for most languages; follow the language ecosystem convention (e.g. `snake_case.py` for Python).
- Variables/functions: follow the dominant convention of the language in use.
- Constants: `SCREAMING_SNAKE_CASE`.

### Comments

Add a comment only when the *why* is non-obvious — a hidden constraint, a workaround for a known upstream bug, or a subtle invariant. Never describe *what* the code does (readable names do that).

---

## CI/CD

Document CI configuration here once pipelines are set up. Typical checks to run on every PR:

- Lint
- Type check
- Unit tests
- Build

---

## Environment Variables

Document required environment variables here as they are introduced. Format:

| Variable | Required | Description |
|---|---|---|
| `NODE_ENV` | No | `development` \| `production` \| `test` |

Never commit `.env` files. Use `.env.example` with placeholder values for documentation.

---

## Security

- Never commit credentials, API keys, tokens, or private keys.
- `.gitignore` must cover common secret files (`.env`, `*.pem`, `*.key`).
- Validate all input at system boundaries (user input, external APIs).
- Avoid eval, dynamic code execution, and SQL string interpolation.
- Dependency updates should be reviewed for supply-chain risk.

---

## Updating This File

Keep CLAUDE.md current as the project evolves. Update it when:

- New tooling, scripts, or build steps are added.
- Branch or PR conventions change.
- New environment variables are introduced.
- Security policies are updated.
- A significant architectural decision is made.
