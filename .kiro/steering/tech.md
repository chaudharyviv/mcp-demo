# Technical Rules — MCP Live Demo

## MCP client architecture

**Use our own MCP client** inside the app for all three servers. Do **not** use OpenAI's hosted MCP tool; it can't reach the stdio ONTAP server.

**Launch the ONTAP server with the app's interpreter** (`sys.executable`), not a bare `python` command. Bare `python` can fail on Streamlit Cloud even when it works locally.

**Open MCP sessions per user turn**, not across Streamlit reruns. Don't store live async sessions in `st.session_state`.

**Namespace tools per server** (`ontap_…`, and prefixes for Learn and GitHub) so the trace shows `MCP › server › tool`.

**Discover GitHub and Learn tools at runtime.** Don't hard-code their tool names or schemas.

## Agent loop

- Max **6** tool iterations per turn
- Temperature **0.2**
- 30 s timeout per request
- One automatic retry on 5xx/429

## State management

**No browser storage** (localStorage/sessionStorage). State lives in `st.session_state`.

## Code conventions

- Python 3.12, type hints throughout, Pydantic models for tool inputs
- Follow the repo layout in `docs/design.md` §7. Keep `app.py` thin (UI only)
- The system prompt lives in `agent/system_prompt.md`, not inline in code
- Tool descriptions: short and precise. The resize tool is described as "plans a resize (dry run)"
- Tool errors are actionable: unknown names return close matches; a bad change number explains the expected format (`CHG` + 7 digits)
- Every ONTAP tool response includes `"synthetic": true`

## Testing

Required per milestone. See `docs/spec.md` for acceptance criteria.
