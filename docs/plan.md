# MCP Live Demo — Plan

> Companion docs: `spec.md` (what to build) · `design.md` (how it fits together)

## 1. Objective

Deliver a **10-minute live demo from a Streamlit Cloud UI** showing how the Model Context Protocol (MCP) lets one AI assistant work across several systems through a single standard connector, including a storage estate, with guardrails.

**One-line story for the audience:**
> "One AI assistant, plugged into three systems through one universal connector — our storage estate included — with guardrails."

**Audience:** business and technology managers. The demo must be presentable, not tech-heavy.

## 2. Scope

### In scope
- Streamlit Cloud app as the only presentation surface (no slides)
- One LLM: **OpenAI GPT-4o mini**
- Three MCP servers:
  - Microsoft Learn (public, remote, no auth)
  - GitHub (public, remote, read-only token)
  - **Mock NetApp ONTAP** (own FastMCP server, stdio subprocess, synthetic data)
- Guarded "write" tool that only produces dry-run plans
- Replay mode, reset, and presenter-friendly UI

### Out of scope (phase 2)
- A real NetApp system (none available; all ONTAP data is synthetic)
- Second LLM / failover (Claude Haiku 4.5)
- Hosting the ONTAP server as a remote HTTP endpoint (Cloud Run)
- Authentication for app users

## 3. Key decisions

| # | Decision | Reason |
|---|---|---|
| D1 | Single model: GPT-4o mini | Less build and rehearsal effort; replay mode already covers API failure |
| D2 | Own MCP client inside the app (not OpenAI-hosted MCP) | The stdio ONTAP server isn't reachable from OpenAI's side; one tool layer for all servers |
| D3 | ONTAP server runs as a stdio subprocess | Streamlit Cloud exposes one port; stdio still exercises the real protocol |
| D4 | Mock data shaped on NetApp's public ONTAP REST API | Credible to storage experts; later swap to a real cluster without changing tool signatures |
| D5 | 100% synthetic data, visibly labelled | Regulated-bank context; public repo and public URL |
| D6 | Write tool is dry-run only and change-number-gated | Showcases governance; nothing is ever "executed" |

## 4. Milestones and build order

| Phase | Work | Output | Est. |
|---|---|---|---|
| M1 | Mock ONTAP dataset + FastMCP server (4 tools, 1 resource) | Server passes MCP Inspector checks | 1–1.5 days |
| M2 | MCP client layer connecting all three servers | Tool discovery lists all tools | 0.5 day |
| M3 | Agent loop on GPT-4o mini with tool calling | All demo prompts work in a plain chat | 1 day |
| M4 | Streamlit UI: landing panel, sidebar, chips, live trace, closing card | Presentable end-to-end app | 1 day |
| M5 | Replay mode, reset, error handling, prompt tuning | Demo is failure-tolerant | 0.5–1 day |
| M6 | Deploy to Streamlit Cloud + backup deployment | Two working URLs | 0.5 day |
| M7 | Rehearsals (5+ full runs, timed) | Stable, timed run of show | 1 day |

**Total:** roughly 5–7 working days.

## 5. Run of show (10 minutes)

| Time | Beat | On screen | Chip |
|---|---|---|---|
| 0:00–1:15 | Hook | Landing panel: story line, three system cards | "Start demo" |
| 1:15–2:15 | Act 1: Knowledge | Microsoft Learn answer with docs link | `1 · Docs` |
| 2:15–3:15 | Act 2: Work system | Repo activity: latest commits + open issues/PRs (several tools in one turn); open trace once | `2 · GitHub` |
| 3:15–8:00 | **Act 3: Our storage (hero)** | Health check finds 3 issues → resize refused → approved with CR as dry-run | `3a · Health` → `3b · Resize` → `3c · Approve` |
| 8:00–9:15 | Wrap up | Closing card with takeaways | `Wrap up` |
| 9:15–10:00 | Buffer / Q&A | — | — |

**Drop order if short on time:** Act 2 first. Never drop Act 3.

### Closing card talking points
- The ONTAP tools mirror the public ONTAP REST API structure, so connecting a real cluster is an implementation step, not a redesign.
- Read-only by default; any change is gated by a change number and shown as a plan first.
- Every tool call is visible and logged.
- The agent layer is model-agnostic; the same MCP server works in any MCP client.
- No production system or data was needed to build or demo this.

## 6. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Streamlit Cloud app asleep / slow cold start | High | Open the app 15 minutes before; keep a backup deployment URL |
| OpenAI API error or rate limit live | Low–Med | Replay mode per chip; spend cap set |
| Non-deterministic agent behaviour | Med | Low temperature; tested chip prompts; strict system prompt; 5+ rehearsals |
| GitHub token expired or revoked | Med | Check token the day before; Act 2 is droppable |
| Network latency (app hosted outside India) | Med | Rehearse on the presenting network; stream tool steps so waits feel active |
| Screen-share blurs small text | Med | Wide layout, larger fonts, 125% browser zoom, test in the meeting tool |
| Audience assumes real systems | Med | "Demo data — no real systems" badge; say it in the hook |

## 7. Pre-demo checklist

**Day before**
- [ ] GitHub token valid; OpenAI key and spend cap valid
- [ ] Both deployments green; replay recordings up to date
- [ ] Full timed rehearsal on the presenting network and meeting tool

**T-15 minutes**
- [ ] Open main app URL, click through landing panel (wakes the app)
- [ ] Press "Reset demo"
- [ ] Browser zoom 125%, notifications off, other tabs closed
- [ ] Backup URL open in a second tab

## 8. Phase 2 (after the demo)

1. Add Claude Haiku 4.5 as a fallback model with per-turn failover and a "simulate outage" beat.
2. Deploy the ONTAP MCP server as a remote streamable-HTTP service on Cloud Run so other MCP clients can use it.
3. Validate tool responses against a NetApp ONTAP simulator.
4. Add an evaluation set (10 read-only questions with verifiable answers) for regression testing.
