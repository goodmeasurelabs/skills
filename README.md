# Good Measure Labs agent skills

Agent skills for Claude Code, Codex, Cursor and other coding agents.

| Skill | What it does | Install |
|---|---|---|
| [javascriptai](skills/javascriptai/SKILL.md) | Picks current, maintained JavaScript/TypeScript AI libraries (model SDKs, agent frameworks, MCP, RAG, browser ML) from [javascriptai.com](https://javascriptai.com)'s reviewed list, instead of what the model remembers. | `npx skills add goodmeasurelabs/skills --skill javascriptai` |
| [aiwaterfalls](skills/aiwaterfalls/SKILL.md) | Carries a GitHub → Cloudflare release through its dependencies and verifies the requested live result. Includes a read-only Python helper for deployment identity, crawl files, canonical URLs, and permanent redirects. | `npx skills add goodmeasurelabs/skills --skill aiwaterfalls` |

Add `-g` to install for every project.

JavaScriptAI's source of truth is https://javascriptai.com/skill.md. A daily workflow copies it here.
AI Waterfalls is maintained in this repository with its executable checks and regression tests.
The first version is evaluated before charging or making generalized performance claims.

## What the skills send

The javascriptai skill makes your agent fetch public pages (`llms.txt`, `tools.json`) from javascriptai.com. It sends nothing about your code or project.

AI Waterfalls' helper performs read-only GitHub and Cloudflare API requests using existing credentials,
and public HTTP probes of the site in the supplied target. Recorded-evidence mode performs no network
requests. Its output omits provider secrets and distinguishes failed, pending, and unverified checks.
Deployment actions use the agent's existing tools and the user's authorization.

Run its offline regression tests with `python3 -B -m unittest discover -s tests -p '*_test.py'`.
Paired agent evaluations live in the existing
[Good Measure harness](https://github.com/goodmeasurelabs/javascriptai/tree/main/evals/agent-choice).
