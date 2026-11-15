# Good Measure Labs agent skills

Agent skills for Claude Code, Codex, Cursor and other coding agents.

| Skill | What it does | Install |
|---|---|---|
| [javascriptai](skills/javascriptai/SKILL.md) | Picks current, maintained JavaScript/TypeScript AI libraries (model SDKs, agent frameworks, MCP, RAG, browser ML) from [javascriptai.com](https://javascriptai.com)'s reviewed list, instead of what the model remembers. | `npx skills add goodmeasurelabs/skills --skill javascriptai` |
| [ineedadistraction](skills/ineedadistraction/SKILL.md) | Sets up a game from [ineedadistraction.com](https://www.ineedadistraction.com/agent) that you play while your agent works. It pauses the moment the agent finishes or needs you. The skill installs a small plugin for Claude Code or Codex that provides the pause signal. | `npx skills add goodmeasurelabs/skills --skill ineedadistraction` |

Add `-g` to install for every project.

Each skill's source of truth is its website (https://javascriptai.com/skill.md, https://www.ineedadistraction.com/skill.md). A daily workflow copies it here, so this repo always matches the live skill.

## What the skills send

The javascriptai skill makes your agent fetch public pages (`llms.txt`, `tools.json`) from javascriptai.com. It sends nothing about your code or project.

The ineedadistraction skill has your agent install a plugin whose hooks report three things to ineedadistraction.com: whether the agent is working, waiting or idle, why it is waiting (done, permission, question), and which agent it is, under a random pairing token. It never sends prompts, file paths, code or tool input.
