# PROGRESS.md — Build log and handoff state

> Every AI tool updates this file at the end of **every** session (see `AGENTS.md` §8).
> Newest session entries go at the **top** of the session log.

## 1. Current state (keep this section short and current)

- **Active tool:** _Antigravity_
- **Current milestone:** _M1 — Mock ONTAP server_
- **Last good commit / tag:** _none yet_
- **Tests:** _not yet run_
- **Next step (one concrete action):**
  > _Create repo skeleton per docs/design.md §7, then generate `ontap_mock/data/estate.json` from docs/spec.md §3 and write the data consistency test._

## 2. Milestone status

| ID | Milestone | Status | Tag | Built with | Notes |
|---|---|---|---|---|---|
| M1 | Mock ONTAP dataset + FastMCP server (4 tools, 1 resource) + tests | ⬜ Not started | | | |
| M2 | MCP client layer (Learn, GitHub, ONTAP) | ⬜ Not started | | | |
| M3 | Agent loop on GPT-4o mini | ⬜ Not started | | | |
| M4 | Streamlit UI (landing, sidebar, chips, trace, closing card) | ⬜ Not started | | | |
| M5 | Replay mode, reset, error handling, prompt tuning | ⬜ Not started | | | |
| M6 | Deploy to Streamlit Cloud + backup deployment | ⬜ Not started | | | |
| M7 | Rehearsals (5+ timed runs) | ⬜ Not started | | | Human task |

Status key: ⬜ Not started · 🟨 In progress · ✅ Done (tests pass, tagged) · 🟥 Blocked

## 3. Environment (fill in at M1, then don't change without approval)

| Item | Value |
|---|---|
| Python | 3.12 |
| streamlit | _pin at M1_ |
| openai | _pin at M1_ |
| fastmcp | _pin at M1_ |
| pydantic | _pin at M1_ |
| pytest | _pin at M1_ |
| Streamlit Cloud main URL | _set at M6_ |
| Streamlit Cloud backup URL | _set at M6_ |
| GitHub demo repo | _name of the public demo repo with seeded MCP-related issues_ |

## 4. Demo acceptance checklist (from docs/spec.md §5)

| Chip | Local | Deployed | Replay recorded | Notes |
|---|---|---|---|---|
| `1 · Docs` — Microsoft Learn answer with link | ⬜ | ⬜ | ⬜ | |
| `2 · GitHub` — MCP-related issues from demo repo | ⬜ | ⬜ | ⬜ | |
| `3a · Health` — aggr_a01 91%, vol_legacy_ftp offline, vol_reports snapshot overrun | ⬜ | ⬜ | ⬜ | |
| `3b · Resize` — tool called without change_id, REFUSED shown in trace | ⬜ | ⬜ | ⬜ | |
| `3c · Approve` — dry run, ~92% projected, aggr_a02 suggested, executed: false | ⬜ | ⬜ | ⬜ | |
| `Wrap up` — closing card, no LLM call | ⬜ | ⬜ | n/a | |

## 5. Decisions made during the build

Decisions that refine (not change) the docs. Anything that changes `docs/` needs human approval first.

| Date | Decision | Why | Made in |
|---|---|---|---|
| | | | |

## 6. Known issues / blockers

| ID | Issue | Severity | Found in | Status |
|---|---|---|---|---|
| | | | | |

## 7. Session log (newest first)

Copy this template for each session:

```
### YYYY-MM-DD — <Tool name> — <Milestone>
- Done:
- Tests: <passed / failed — list failures>
- Files touched:
- Commit / tag:
- Issues found:
- Next step (one concrete action):
- Credits left (approx.): <if the tool is close to its limit, say so>
```

_(no sessions yet)_

## 8. Handoff notes for the next tool

_Write anything the next tool must know that isn't obvious from the code: half-finished work, traps you hit, things you tried that didn't work._

- 
