---
name: ineedadistraction
description: Sets up and opens a game the user plays while you work; it pauses by itself the moment you finish or need them. Use when the user asks for a distraction, a game, or something to do while their agent runs, or wants to install, open or turn off the I Need a Distraction game sync.
---

# I Need a Distraction

A browser arcade at https://www.ineedadistraction.com that pairs with a coding agent. While you work the user plays; when you finish a turn, ask a question or need a permission, the game pauses and tells them.

## Install (once)

The pause and resume signals come from a plugin with lifecycle hooks, so installing this skill alone is not enough. Tell the user what you are about to install, then run the pair of commands for the agent you are.

Claude Code:

```
claude plugin marketplace add goodmeasurelabs/ineedadistraction
claude plugin install distraction@ineedadistraction
```

Codex:

```
codex plugin marketplace add goodmeasurelabs/ineedadistraction
codex plugin add distraction@ineedadistraction
```

In Codex the user must then run `/hooks` once to review and trust the plugin's hooks. The plugin takes effect in the next session.

## Open the game

Once the plugin is installed, the arcade opens by itself on the first prompt of a session. To open it on request, run the plugin's `scripts/open.sh`, which prints the paired link. Keep working afterwards; do not wait for the user to play.

Without the plugin, the user can still play unpaired at https://www.ineedadistraction.com.

## Controls

- Stop it opening by itself: `touch ~/.config/ineedadistraction/no-auto-open`
- Turn the sync off: `touch ~/.config/ineedadistraction/off` (delete the file to turn it back on)

## What is sent

Only the word `working`, `waiting` or `idle`, a one-word reason, which agent it is, and a random pairing token made on the user's machine. Never prompts, file paths, code or tool input.
