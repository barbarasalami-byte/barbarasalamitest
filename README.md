# barbarasalamitest

Research tooling, in two independent pieces. Take either.

## `.claude/skills/literature-review/`

A drop-in Agent Skill. Copy the directory into any Claude project
(`.claude/skills/`) and it triggers on literature-review requests, adapting to
whatever retrieval tools that session has — web search, MCP servers, database
clients, an internal corpus. No code, no dependencies.

## `research_core/`

The same method as a Python package, for when you need it in an application
rather than a Claude session. Source-agnostic: register the sources you have
and the agent builds its tools, prompt, and citation checks around them.
See `research_core/README.md`.

Both carry the same non-negotiable: every identifier cited must have been
retrieved during the run. `research_core` enforces it in code
(`audit_citations`); the skill enforces it by instruction.

Methodology adapted from [ECC](https://github.com/affaan-m/ECC) (MIT) — see the
`NOTICE.md` files.

## Tests

    python -m unittest discover -s tests

Offline only: no network, no API key.
