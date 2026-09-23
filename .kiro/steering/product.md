# Product Rules — MCP Live Demo

This is a **10-minute live demo app on Streamlit Cloud** showing an AI assistant (OpenAI GPT-4o mini) using tools from three MCP servers through an in-app MCP client:

1. **Microsoft Learn MCP**: remote, no auth
2. **GitHub MCP**: remote, read-only token
3. **Mock NetApp ONTAP MCP**: our own FastMCP server, stdio subprocess, **synthetic data only**

## Scope (frozen)

Exactly three MCP servers, one LLM (GPT-4o mini). Do **not** add servers, models, databases, auth, or features not in `docs/spec.md`.

## Key guardrail

A storage change request is **refused by the tool** without a change number, then returns a **dry-run plan** with one. Nothing is ever executed.

The guardrail lives **inside the tool**, not only in the system prompt.

## Data and secrets

- **Synthetic data only:** no real hostnames, IPs, company names, internal system names, or data from any employer environment, anywhere in code, data, comments, or commits.
- **`ontap_vol_resize` is dry-run only:** it must never modify the dataset and must always return `executed: false`. There is no execution path, now or "for later".
- **Secrets** (`OPENAI_API_KEY`, `GITHUB_PAT`, `GITHUB_DEMO_REPO`) come from Streamlit secrets or environment variables only. Never hard-code, log, or commit them. `.streamlit/secrets.toml` stays in `.gitignore`.

## Field specification

**Don't invent ONTAP fields.** Use only the fields listed in `docs/spec.md` §3. If a field seems missing, ask before implementing.

## Code structure

**Don't restructure working code.** Extend it. Ask before changing the file layout, renaming modules, or rewriting something another session built.

## Dependencies

**Pinned dependencies:** versions are pinned in `requirements.txt` and recorded in `PROGRESS.md`. Don't upgrade or add packages without asking.
