# MCP Live Demo — Specification

> Companion docs: `plan.md` (why and when) · `design.md` (how it fits together)

## 1. System summary

A Streamlit Cloud app hosts a chat-based AI agent (GPT-4o mini). The agent uses tools from three MCP servers through an in-app MCP client. One of those servers is a self-built FastMCP server simulating NetApp ONTAP with synthetic data.

## 2. Functional requirements

### 2.1 LLM

| ID | Requirement |
|---|---|
| LLM-1 | Model: OpenAI `gpt-4o-mini`, temperature 0.2 |
| LLM-2 | Tool calling via the app's own MCP client; tool schemas taken from MCP `list_tools` |
| LLM-3 | Max 6 tool-call iterations per user turn; then answer with what's known |
| LLM-4 | Per-request timeout 30 s; one automatic retry on 5xx/429, then show a friendly error and offer replay |

### 2.2 System prompt rules

The agent must:
1. Use tools to answer anything about docs, repos, or storage; never guess or invent data.
2. Answer in **4–6 lines**, bolding the single most important number or finding.
3. Never state or imply that a change was executed. Changes are only ever described as dry-run plans.
4. When citing ONTAP data, note it comes from the demo environment (synthetic).
5. For any change request without a change number, ask for one; don't call the resize tool with an invented number.
6. Prefer one summarising tool call (`ontap_cluster_health_summary`) before drilling down.

### 2.3 MCP servers

| ID | Server | Transport | Endpoint / launch | Auth |
|---|---|---|---|---|
| MCP-1 | Microsoft Learn | Streamable HTTP | `https://learn.microsoft.com/api/mcp` | None |
| MCP-2 | GitHub | Streamable HTTP | `https://api.githubcopilot.com/mcp/` | Bearer fine-grained PAT, read-only, scoped to one demo repo |
| MCP-3 | Mock ONTAP | stdio | Launched by the app as a Python subprocess | None |

- On app start, the client connects to all three and caches the tool list for the sidebar.
- If a server fails to connect, the sidebar shows it red and the app keeps working with the others.

### 2.4 Mock ONTAP server — tools

All tools use the `ontap_` prefix, Pydantic-validated inputs, and return JSON with a top-level `"synthetic": true`.

#### `ontap_cluster_health_summary`
- **Annotations:** readOnly, idempotent
- **Input:** `cluster` (optional string)
- **Output:** per-cluster counts (aggregates, SVMs, volumes), plus an `issues` list. Each issue has `severity` (`critical`/`warning`), `object_type`, `object_name`, `message`.
- **Issue rules:**
  - Aggregate used ≥ 90% → critical; ≥ 85% → warning
  - Volume `state` ≠ `online` → critical
  - Volume snapshot used > snapshot reserve → warning
  - Volume used ≥ 90% of size → warning

#### `ontap_aggr_show`
- **Annotations:** readOnly, idempotent
- **Input:** `cluster` (optional), `min_used_percent` (optional int 0–100)
- **Output:** list of aggregates with fields in §3.2, sorted by used % descending

#### `ontap_vol_show`
- **Annotations:** readOnly, idempotent
- **Input:** `cluster`, `svm`, `aggregate`, `state`, `name` (all optional); `limit` (default 20)
- **Output:** list of volumes with fields in §3.3

#### `ontap_vol_resize`
- **Annotations:** readOnly (never mutates data), not destructive
- **Input:** `volume` (required), `grow_by_gb` (required int 1–5000), `change_id` (optional string)
- **Behaviour:**
  - `change_id` missing → `status: "refused"`, message: "A change number is required (format CHG followed by 7 digits)."
  - `change_id` present but not matching `^CHG\d{7}$` → `status: "refused"`, message explaining the expected format
  - Unknown volume → `status: "error"`, message listing close matches
  - Valid → `status: "dry_run"` with a plan: current size, new size, aggregate, current and projected aggregate used %, a `warnings` list, and `executed: false`
  - If projected aggregate used % ≥ 90, add warning: "Aggregate would remain above 90%; consider moving the volume to a less-used aggregate." Suggest the least-used aggregate on the same cluster.
- **Never** modifies the dataset.

#### Resource: `ontap://inventory/summary`
Read-only resource returning cluster, SVM, and aggregate names (no volume detail).

## 3. Mock data specification

Stored as one JSON file loaded at server start. All names are invented. Sizes are in bytes in the data file (ONTAP style); tables below show TiB for readability.

**Consistency rule:** the sum of volume footprints on an aggregate equals the aggregate's `used` value.

### 3.1 Clusters and SVMs

| Cluster | Nodes | SVMs |
|---|---|---|
| `cls-alpha` | `alpha-01`, `alpha-02` | `svm_core`, `svm_shared` |
| `cls-beta` | `beta-01`, `beta-02` | `svm_ops`, `svm_legacy` |

### 3.2 Aggregates

Fields: `name`, `uuid`, `node.name`, `state`, `space.block_storage.size`, `space.block_storage.used`, `space.block_storage.available`, plus derived `used_percent`.

| Aggregate | Cluster | Node | Size | Used | Used % | Planted issue |
|---|---|---|---|---|---|---|
| `aggr_a01` | cls-alpha | alpha-01 | 20.0 | 18.2 | **91%** | Critical capacity |
| `aggr_a02` | cls-alpha | alpha-02 | 20.0 | 11.0 | 55% | — |
| `aggr_b01` | cls-beta | beta-01 | 30.0 | 16.5 | 55% | — |
| `aggr_b02` | cls-beta | beta-02 | 15.0 | 9.0 | 60% | — |

### 3.3 Volumes

Fields: `name`, `uuid`, `svm.name`, `aggregates[].name`, `state`, `style`, `size`, `space.used`, `space.available`, `space.snapshot.reserve_percent`, `space.snapshot.used`, plus derived `used_percent` and `footprint`.

| Volume | SVM | Aggregate | Size | Used | Footprint | State | Note |
|---|---|---|---|---|---|---|---|
| `vol_payments_db` | svm_core | aggr_a01 | 6.0 | 5.64 (94%) | 5.8 | online | Resize target; nearly full |
| `vol_ledger_archive` | svm_core | aggr_a01 | 6.0 | 4.7 | 4.9 | online | |
| `vol_core_logs` | svm_core | aggr_a01 | 4.0 | 3.3 | 3.5 | online | |
| `vol_batch_stage` | svm_shared | aggr_a01 | 5.0 | 3.8 | 4.0 | online | |
| `vol_hr_share` | svm_shared | aggr_a02 | 4.0 | 2.8 | 3.0 | online | |
| `vol_app_bin` | svm_shared | aggr_a02 | 3.0 | 2.3 | 2.5 | online | |
| `vol_reports` | svm_shared | aggr_a02 | 4.0 | 2.6 | 3.5 | online | **Snapshots 18% vs 5% reserve** |
| `vol_test_clone` | svm_core | aggr_a02 | 3.0 | 1.8 | 2.0 | online | |
| `vol_mq_data` | svm_ops | aggr_b01 | 8.0 | 5.6 | 6.0 | online | |
| `vol_risk_models` | svm_ops | aggr_b01 | 7.0 | 5.2 | 5.5 | online | |
| `vol_dr_replica` | svm_ops | aggr_b01 | 6.0 | 4.7 | 5.0 | online | |
| `vol_legacy_ftp` | svm_legacy | aggr_b02 | 3.0 | 1.9 | 2.0 | **offline** | Offline volume |
| `vol_user_home` | svm_legacy | aggr_b02 | 5.0 | 3.8 | 4.0 | online | |
| `vol_ci_cache` | svm_ops | aggr_b02 | 4.0 | 2.8 | 3.0 | online | |

**Expected health result:** 1 critical aggregate (`aggr_a01`), 1 critical offline volume (`vol_legacy_ftp`), 1 warning snapshot overrun (`vol_reports`), 1 warning near-full volume (`vol_payments_db`).

**Expected resize dry-run** (`vol_payments_db`, +200 GB, `CHG0012345`): size 6.0 → ~6.2 TiB; `aggr_a01` projected ~92%; warning to consider `aggr_a02` (55%).

> Field names should be checked against NetApp's public ONTAP REST API documentation before finalising.

## 4. UI requirements

| ID | Requirement |
|---|---|
| UI-1 | Wide layout; base font enlarged for screen share |
| UI-2 | **Landing panel** shown before first message: story line, three system cards, "Start demo" button |
| UI-3 | **Sidebar:** connected systems with status dot and tool count; model name; "Demo data — no real systems" badge; collapsed "Presenter" expander with Replay mode, Reset demo |
| UI-4 | **Chip row** above chat input with the demo prompts in §5, in order |
| UI-5 | **Live trace:** each tool call streams as a step ("Mock ONTAP → `ontap_aggr_show` … done, 0.3 s"); expandable to show arguments and a trimmed result |
| UI-6 | **Presenter mode** (default on): hides raw JSON in traces |
| UI-7 | **Closing card:** a "Wrap up" chip renders static takeaways (see plan.md §5) |
| UI-8 | **Reset demo:** clears chat and session state, returns to landing panel |
| UI-9 | **Replay mode:** chips return recorded answers and traces with the same visual pacing |

## 5. Demo prompts and acceptance criteria

| Chip | Prompt | Must happen |
|---|---|---|
| `1 · Docs` | "How do I restrict public network access to an Azure Storage account? Give me the key steps and the official doc link." | Microsoft Learn tool called; ≤6 lines; includes a learn.microsoft.com link |
| `2 · GitHub` | "What's been happening in our demo repo? Summarise the last 3 commits and tell me if there are any open issues or pull requests." | Several GitHub tools called (commits, issues, PRs), in parallel; names the 3 latest real commits with links; states the open issue/PR count (may be zero) |
| `3a · Health` | "How healthy is our storage estate? Anything I should worry about?" | Calls `ontap_cluster_health_summary`; mentions `aggr_a01` at **91%**, `vol_legacy_ftp` offline, `vol_reports` snapshot overrun |
| `3b · Resize` | "Grow the payments database volume by 200 GB." | Does **not** produce a plan; asks for a change number |
| `3c · Approve` | "Change number is CHG0012345." | Calls `ontap_vol_resize`; presents a dry-run plan with projected ~92% and the aggregate warning; states nothing was executed |
| `Wrap up` | (static) | Closing card renders; no LLM call |

## 6. Non-functional requirements

| ID | Requirement |
|---|---|
| NF-1 | Each chip completes in ≤ 15 s on the presenting network (target ≤ 8 s) |
| NF-2 | Secrets (`OPENAI_API_KEY`, `GITHUB_PAT`, `GITHUB_DEMO_REPO`) in Streamlit secrets only; never in the repo |
| NF-3 | OpenAI spend cap set on the account used |
| NF-4 | No real hostnames, IPs, names, or data from any employer environment anywhere in the repo |
| NF-5 | Every tool call logged (tool, args, duration, status) in session state for the trace |
| NF-6 | App remains usable if any one MCP server is down |

## 7. Out of scope
Real ONTAP connectivity, a second LLM, user authentication, persistent storage, multi-user sessions.
