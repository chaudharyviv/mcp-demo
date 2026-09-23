# AGENTS.md — Rules for AI coding agents

This file applies to **every** AI coding tool used on this repo (Antigravity, Kiro, Claude Code, or any other). Read it fully before doing anything.

## 1. What this project is

A **10-minute live demo app on Streamlit Cloud** showing an AI assistant (OpenAI GPT-4o mini) using tools from three MCP servers through an in-app MCP client:

1. **Microsoft Learn MCP**: remote, no auth
2. **GitHub MCP**: remote, read-only token
3. **Mock NetApp ONTAP MCP**: our own FastMCP server, stdio subprocess, **synthetic data only**

The hero moment: a storage change request is **refused by the tool** without a change number, then returns a **dry-run plan** with one. Nothing is ever executed.

## 2. Read order (every session, before writing code)

1. `AGENTS.md`: this file
2. `PROGRESS.md`: what's done, what's broken, the exact next step
3. `docs/plan.md`: scope, decisions, milestones
4. `docs/spec.md`: requirements, tool contracts, dataset, acceptance criteria
5. `docs/design.md`: architecture, flows, UI, repo layout

**The docs are the source of truth.** If code and docs disagree, stop and ask. Don't silently change either.

## 3. Hard rules (non-negotiable)

1. **Scope is frozen.** Exactly three MCP servers, one LLM (GPT-4o mini). Do not add servers, models, databases, auth, or features not in `docs/spec.md`.
2. **Synthetic data only.** No real hostnames, IPs, company names, internal system names, or data from any employer environment, anywhere in code, data, comments, or commits.
3. **`ontap_vol_resize` is dry-run only.** It must never modify the dataset and must always return `executed: false`. There is no execution path, now or "for later".
4. **The guardrail lives in the tool.** The change-number check is enforced inside `ontap_vol_resize`, not only in the system prompt.
5. **Don't invent ONTAP fields.** Use only the fields listed in `docs/spec.md` §3. If a field seems missing, ask.
6. **Don't restructure working code.** Extend it. Ask before changing the file layout, renaming modules, or rewriting something another session built.
7. **Secrets** (`OPENAI_API_KEY`, `GITHUB_PAT`, `GITHUB_DEMO_REPO`) come from Streamlit secrets or environment variables only. Never hard-code, log, or commit them. `.streamlit/secrets.toml` stays in `.gitignore`.
8. **Pinned dependencies.** Versions are pinned in `requirements.txt` and recorded in `PROGRESS.md`. Don't upgrade or add packages without asking.

## 4. Architecture constraints (common agent mistakes)

- **Use our own MCP client** inside the app for all three servers. Do **not** use OpenAI's hosted MCP tool; it can't reach the stdio ONTAP server.
- **Launch the ONTAP server with the app's interpreter** (`sys.executable`), not a bare `python` command. Bare `python` can fail on Streamlit Cloud even when it works locally.
- **Open MCP sessions per user turn**, not across Streamlit reruns. Don't store live async sessions in `st.session_state`.
- **Namespace tools per server** (`ontap_…`, and prefixes for Learn and GitHub) so the trace shows `MCP › server › tool`.
- **Discover GitHub and Learn tools at runtime.** Don't hard-code their tool names or schemas.
- Agent loop: max **6** tool iterations per turn, temperature **0.2**, 30 s timeout, one retry on 5xx/429.
- **No browser storage** (localStorage/sessionStorage). State lives in `st.session_state`.

## 5. Code conventions

- Python 3.12, type hints throughout, Pydantic models for tool inputs.
- Follow the repo layout in `docs/design.md` §7. Keep `app.py` thin (UI only).
- The system prompt lives in `agent/system_prompt.md`, not inline in code.
- Tool descriptions: short and precise. The resize tool is described as "plans a resize (dry run)".
- Tool errors are actionable: unknown names return close matches; a bad change number explains the expected format (`CHG` + 7 digits).
- Every ONTAP tool response includes `"synthetic": true`.

## 6. Testing (required per milestone)

- **M1:** `pytest` tests for all four ONTAP tools against the expected results in `docs/spec.md` §3:
  - `aggr_a01` at 91% is critical
  - `vol_legacy_ftp` is offline
  - `vol_reports` shows a snapshot overrun
  - resize with no `change_id` returns `refused`
  - resize with a malformed ID returns `refused`
  - resize with `CHG0012345` returns `dry_run`, projected ~92%, with the `aggr_a02` suggestion
  - the dataset is unchanged after any call

  Also a data test: **volume footprints sum to each aggregate's used space**. Also check the server standalone with the MCP Inspector.
- **M2:** tool discovery lists tools from all reachable servers; one unreachable server doesn't crash the app.
- **M3 onward:** each demo chip in `docs/spec.md` §5 passes its acceptance criteria.
- Never mark a milestone done with failing tests. If you must stop with failures, record them in `PROGRESS.md`.

## 7. Workflow

1. Work on **one milestone at a time**, in the order in `docs/plan.md` §4.
2. **Plan before coding.** State which spec sections you're implementing and which files you'll touch; wait for approval if the tool supports it.
3. Keep changes small and reviewable.
4. When a milestone's tests pass:
   - commit with message `M<n>: <summary>`
   - tag it `m<n>-done`
   - update `PROGRESS.md`
5. If a doc seems wrong or ambiguous, **ask**. Don't guess and don't edit `docs/` without approval.

## 8. Handoff protocol (switching tools or ending a session)

Before stopping, **always**:
1. Update `PROGRESS.md`: status table, session log entry, known issues, and **one concrete next step**.
2. Run the tests and record pass/fail in `PROGRESS.md`.
3. Commit and push. Never leave uncommitted work.

The next tool starts with:
> "Read AGENTS.md, PROGRESS.md and docs/. Continue from the next step in PROGRESS.md. Don't restructure existing code."

## 9. Tool-specific entry points

| Tool | Setup |
|---|---|
| **Antigravity** | Add a workspace rule: "Follow AGENTS.md. Read PROGRESS.md and docs/ before any task." Approve plans before execution. |
| **Kiro** | Copy §3–§5 of this file into steering files (product, tech, structure). Load `docs/spec.md` and `docs/design.md` as the feature spec and generate tasks from the milestones not yet done in `PROGRESS.md`. |
| **Claude Code** | Create `CLAUDE.md` containing: "Read AGENTS.md first and follow it. Then read PROGRESS.md and docs/." |

## 10. Definition of done (whole project)

- All six chips in `docs/spec.md` §5 pass on the **deployed** Streamlit Cloud app.
- Replay mode works for every chip with the network to OpenAI blocked.
- The "Demo data — no real systems" badge is visible.
- The main and backup deployments are both green.
