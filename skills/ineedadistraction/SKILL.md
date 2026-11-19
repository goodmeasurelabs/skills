---
name: ineedadistraction
description: Sets up and customizes I Need a Distraction for Codex or Claude Code. Use for pairing, game preferences, Stop distracting, Keep distracting, or a game while the agent works.
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

In Codex, guide the user to review and trust the plugin's hooks in Settings > Hooks or `/hooks`. Follow the installed client's reload instructions. Do not bypass hook trust, and do not report pairing merely because installation completed.

Preference controls require plugin 0.5.0 or newer and Python 3. Locate the installed plugin's `scripts/settings.py` and `scripts/open.sh` using its installation path. If these are missing, update the plugin using the agent's supported plugin manager, then complete any new hook review.

For an existing Codex installation, run `codex plugin marketplace upgrade ineedadistraction`, then `codex plugin add distraction@ineedadistraction`. For Claude Code, run `claude plugin marketplace update ineedadistraction`, then `claude plugin update distraction@ineedadistraction`. Follow the client's restart or hook-review instructions. Refresh the distraction popup once after updating (Cmd+R on macOS, Ctrl+R elsewhere); opening it again only brings the existing window forward.

## Apply the user's chosen mix

Use the preferences supplied in their setup prompt. Supported settings are `--enabled true|false`, `--categories merge,logic,math,arcade`, `--pace any|untimed`, and `--sound true|false`. Each argument is optional and updates only that setting. Default to the available four categories, any pace and muted sound if no preferences were supplied.

```sh
python3 <plugin>/scripts/settings.py set --enabled true --categories merge,logic --pace untimed --sound false
```

The JSON response contains the effective local settings and `synced`. Only `synced: true` confirms the service acknowledged the settings. On failure, explain that local preferences are saved and synchronization is pending; run `sync` to retry. Do not insert pairing tokens into prompts or analytics.

Read the returned effective settings as well as `synced`: a newer Stop from the popup cancels a stale queued On. If the helper reports this conflict, leave distractions Off until the user explicitly asks to enable them again.

Word and memory categories are planned but have no agent-ready games in this version. Difficulty and family-friendly filters are also not implemented yet; do not invent a command for them.

## Open the game

With distractions On, a fresh prompt can open the compact player. On macOS, plugin 0.5.1 checks that the originating coding app or terminal is still in front before raising the player. To open it on request, run `sh <plugin>/scripts/open.sh`, which starts the local control connection and opens `/arcade` with a paired link. The website's `/agent` page is the separate setup experience. Keep working afterwards; do not wait for the user to play.

Verify the settings handshake with `python3 <plugin>/scripts/settings.py sync`; then verify a fresh lifecycle report before claiming automatic pause is working. Ask the user to complete any native hook review that is still required. The popup's separate browser profile receives preferences through the plugin, not through website localStorage.

Without the plugin, the user can still play unpaired at https://www.ineedadistraction.com.

## Controls

- **“Stop distracting”**: `python3 <plugin>/scripts/settings.py off`. Stops automatic popups until explicitly re-enabled, preserving the game mix and saved runs.
- **“Keep distracting”**: `python3 <plugin>/scripts/settings.py on`. Then run `open.sh` if the user wants to play immediately.
- **“Only math games”**: `python3 <plugin>/scripts/settings.py set --categories math`.
- **“No timers”**: `python3 <plugin>/scripts/settings.py set --pace untimed`.
- **“Resume this game”** in the popup dismisses the current interruption without enabling automatic distractions or answering an agent question.

These preferences apply to this computer's pairing across Codex and Claude Code. Reopening a game never silently changes Off to On. The settings connection stays available while Off; after the player has been closed for five minutes, reopen through `open.sh` to reconnect it.

## What is sent

The plugin sends working/waiting/idle state, a short reason, agent type, opaque run/event IDs, timing and return-target type under a random pairing token. Settings synchronization sends enabled, categories, pace, sound, revision and plugin version. Prompts, code, tool input, chat titles and actual return destinations stay on the machine.
