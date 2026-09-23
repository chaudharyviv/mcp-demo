# Structure — MCP Live Demo

## Repository layout

```
mcp-demo/
├── app.py                     # Streamlit entry point (UI only)
├── agent/
│   ├── loop.py                # agent loop, trace events
│   ├── mcp_clients.py         # multi-server MCP client config
│   └── system_prompt.md       # tunable prompt
├── ontap_mock/
│   ├── server.py              # FastMCP server, 4 tools + 1 resource
│   └── data/estate.json       # synthetic dataset
├── replay/                    # recorded chip responses
├── ui/
│   ├── landing.py
│   ├── sidebar.py
│   ├── closing_card.py
│   └── trace.py
├── tests/                     # pytest test suite per milestone
├── requirements.txt
├── .streamlit/config.toml     # theme, wide layout
├── .streamlit/secrets.toml.example    # template for secrets
├── README.md                  # includes "all data is synthetic"
├── docs/
│   ├── spec.md               # requirements
│   ├── design.md             # architecture
│   └── plan.md               # milestones
└── PROGRESS.md               # build log and handoff
```

## What to extend, not restructure

- Existing modules in `agent/`, `ui/`, `ontap_mock/` — add to them, don't rename or reorganize
- The test suite structure — add new test files per milestone, don't consolidate
- `agent/system_prompt.md` — tune it, don't move it
- The replay recording format in `replay/*.json` — extend the schema if needed, don't change storage

## Milestones and workflow

Work on one milestone at a time, in order from `docs/plan.md` §4. Plan before coding, commit when tests pass, tag with `m<n>-done`, and update `PROGRESS.md`.
