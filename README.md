# MCP Live Demo

A Streamlit app for a 10-minute live demo: one AI assistant (OpenAI GPT-4o mini) uses tools from three systems through the **Model Context Protocol (MCP)**, including a storage estate, with guardrails.

> **All data is synthetic.** The NetApp ONTAP server is a mock with an invented dataset. No real hostnames, IPs, company names or data from any real environment appear anywhere in this repo, and the app says so on screen ("Demo data — no real systems").

## What it shows

| Server | What it is | Transport | Access |
|---|---|---|---|
| **Microsoft Learn** | Public documentation search | Streamable HTTP | No auth |
| **GitHub** | Commits, issues and PRs in one demo repo | Streamable HTTP | **Read-only** endpoint + read-only token |
| **Mock ONTAP** | Our own FastMCP server over a synthetic storage estate | stdio subprocess | Local |

The key moment: when asked to grow a volume, the assistant **won't produce a plan without a change number**. With one (`CHG` + 7 digits), the resize tool returns a **dry-run plan only** (`executed: false`). The change-number check is enforced inside the tool itself, not just in the prompt, and no code path can modify the data.

The app runs its own MCP client for all three servers. It doesn't use OpenAI's hosted MCP tool, which can't reach a local stdio server.

## Quick start (local)

Requires **Python 3.12**.

```bash
python -m venv venv
# Windows:        venv\Scripts\activate
# macOS / Linux:  source venv/bin/activate
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml` from the template (it's git-ignored; never commit it):

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

| Key | Needed for | Notes |
|---|---|---|
| `OPENAI_API_KEY` | Every chip except Wrap up | Set a spend cap on the account |
| `GITHUB_PAT` | Chip 2 | Fine-grained, **read-only**, scoped to the demo repo |
| `GITHUB_DEMO_REPO` | Chip 2 | `owner/repo`; any repo with a few commits works (open issues/PRs are optional) |

All values must be quoted strings (`KEY = "value"`), or Streamlit can't read the file. Environment variables with the same names take precedence over `secrets.toml`.

Run it:

```bash
streamlit run app.py
```

If a server can't connect, the sidebar shows it red and the app keeps working with the others.

## Running the demo

Click **Start Demo**, then use the chips in order:

| Chip | What happens |
|---|---|
| `1 · Docs` | Microsoft Learn answer with an official doc link |
| `2 · GitHub` | The demo repo's 3 latest commits plus its open issue/PR count, from several GitHub tools called in parallel |
| `3a · Health` | Storage health: `aggr_a01` at 91%, `vol_legacy_ftp` offline, `vol_reports` snapshot overrun |
| `3b · Resize` | "Grow the payments database volume by 200 GB" → asks for a change number, no plan |
| `3c · Approve` | With `CHG0012345` → dry-run plan: ~92% projected, suggests `aggr_a02`, **nothing executed** |
| `Wrap up` | Static closing card, no model call |

Each tool call streams into a live trace (`Mock ONTAP → ontap_vol_resize · 0.3 s ✓`). The sidebar lists every server's tools. GitHub shows all its tools but only the read-only ones are enabled; write tools such as `merge_pull_request` are listed as blocked and never offered to the model.

**Presenter settings** (collapsed in the sidebar):
- **Replay mode:** chips play back recorded answers and traces from `replay/` with live-like pacing. Use it if the network or OpenAI is unreliable.
- **Presenter mode** (on by default): hides raw arguments and JSON in traces.
- **Reset demo:** clears the chat, returns to the landing panel and re-checks server connections.

If OpenAI fails mid-demo, the app shows a short error and a **Show recorded answer** button.

## Mock ONTAP server

`ontap_mock/server.py` is a FastMCP server over `ontap_mock/data/estate.json`, with field names shaped on NetApp's public ONTAP REST API:

| Tool | Purpose |
|---|---|
| `ontap_cluster_health_summary` | Counts plus a list of critical/warning issues |
| `ontap_aggr_show` | Aggregates, sorted by used % |
| `ontap_vol_show` | Volumes, with filters |
| `ontap_vol_resize` | Plans a resize (dry run). Refuses without a valid change number; `grow_by_gb` must be 1–5000 |

There's also a resource, `ontap://inventory/summary`. Every response includes `"synthetic": true`, and the dataset is re-read on each call and never written.

To try the server on its own, e.g. with the MCP Inspector:

```bash
python ontap_mock/server.py
```

## Tests

```bash
python -m pytest -q
```

The suite covers the ONTAP tools and guardrail (including "dataset unchanged after every call"), the MCP client, the agent loop, and the UI via Streamlit's `AppTest`. No OpenAI key is needed. A few tests need internet access (Microsoft Learn discovery).

## Deploying to Streamlit Cloud

1. Point a new app at this repo with `app.py` as the entry file, and choose **Python 3.12** under advanced settings.
2. Paste the three secrets into the app's **Secrets** settings (same TOML format).
3. Keep a second deployment as a backup URL, and open the app about 15 minutes before presenting to wake it up.

Dependencies are pinned in `requirements.txt`. Don't loosen the pins: for example, `openai==1.52.0` breaks with `httpx` 0.28, which is why `httpx` is pinned.

## Repository layout

```
app.py                  Streamlit entry point (UI wiring only)
agent/
  loop.py               Agent loop: GPT-4o mini, max 6 tool iterations, 30 s timeout, one retry
  mcp_clients.py        MCP client for all three servers (sessions opened per turn)
  settings.py           Secret lookup: environment, then Streamlit secrets
  system_prompt.md      The system prompt (tunable without code changes)
ontap_mock/
  server.py             Mock ONTAP FastMCP server: 4 tools + 1 resource
  data/estate.json      Synthetic dataset
replay/                 Recorded chip answers and traces for replay mode
ui/                     Landing panel, sidebar, chips, trace, closing card
tests/                  pytest suite
docs/                   plan.md, spec.md, design.md: the source of truth
```

## Further reading

- `docs/plan.md`: scope, decisions and run of show
- `docs/spec.md`: requirements, tool contracts, dataset and acceptance criteria
- `docs/design.md`: architecture, flows and UI
- `AGENTS.md`: rules for AI coding tools working on this repo
- `PROGRESS.md`: build status, known issues and next steps
