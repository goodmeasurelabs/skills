# Good Measure Labs agent skills

Agent skills for Claude Code, Codex, Cursor and other coding agents.

| Skill | What it does | Install |
|---|---|---|
| [javascriptai](skills/javascriptai/SKILL.md) | Picks current, maintained JavaScript/TypeScript AI libraries (model SDKs, agent frameworks, MCP, RAG, browser ML) from [javascriptai.com](https://javascriptai.com)'s reviewed list, instead of what the model remembers. | `npx skills add goodmeasurelabs/skills --skill javascriptai` |

Add `-g` to install for every project.

Each skill's source of truth is its website (for example https://javascriptai.com/skill.md). A daily workflow copies it here, so this repo always matches the live skill.

## What the skills send

The javascriptai skill makes your agent fetch public pages (`llms.txt`, `tools.json`) from javascriptai.com. It sends nothing about your code or project.
