# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kagemusha is a Slack monitoring daemon that watches for mentions, DMs, and thread replies directed at the user. When relevant messages are detected, it invokes Claude CLI (`claude -p`) with a prompt template to classify and handle requests (spec questions, dev tasks, MCP tool work, general knowledge, etc.).

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the monitor
python -m monitor.main
# or
./run.sh

# Setup
cp .env.example .env  # then fill in values
```

There are no test or lint commands configured.

## Architecture

```
monitor/
├── main.py           # Polling loop & orchestration (3-stage: mentions → tracked threads → DMs)
├── config.py         # .env loading, validation, Slack user_id resolution
├── slack_client.py   # Slack SDK wrapper (search, history, replies, channel caching)
├── state.py          # JSON-based state persistence (processed IDs, thread tracking, TTL expiry)
├── skill_invoker.py  # Spawns `claude -p` subprocess with prompt template
└── message_filter.py # Classifies messages (system, bot, self, relevant DM)
```

**Polling cycle** (runs every `POLL_INTERVAL` seconds, default 60s):
1. `_search_mentions()` — Slack Search API for @mentions across channels/threads (filtered by `SLACK_CHANNEL_IDS` if set)
2. `_poll_tracked_threads()` — checks threads where user was mentioned for new replies (also filtered by `SLACK_CHANNEL_IDS`)
3. `_poll_dms()` — polls DM channels for new non-bot messages (includes self-DM support)

Each relevant message triggers `invoke_skill()` which reads the prompt template, substitutes `{{channel_id}}` and `{{message_ts}}`, and runs Claude CLI with `--enable-auto-mode`.

### Prompt Template

- `prompt_template.md` — default template (committed, git管理)
- `prompt_template.local.md` — local override, takes priority if present (gitignored)

`skill_invoker.py` checks for `prompt_template.local.md` first; if it exists, it is used instead of `prompt_template.md`. This allows local customization without affecting the committed template.

**注意**: `prompt_template.md` はgit管理されているため、個人やプロジェクト固有のカスタマイズは `prompt_template.local.md` に記述すること。`prompt_template.md` を直接編集しないこと。

### workspace/ Directory

Claude CLI runs from `workspace/` (not the project root) to avoid loading the development-focused `CLAUDE.md`. A `.claude` symlink in `workspace/` points to the project's `.claude/` directory so that skills and settings remain accessible.

### Skills

Located in `.claude/skills/`:
- `slack-toolkit/` — Slack message reading, sending, reactions, and file downloads

**State management**: Atomic JSON file writes. Tracks processed message IDs (TTL-based dedup), channel timestamps, and monitored threads (default 5-day TTL).

## Tech Stack

- Python 3.6+ with `slack_sdk` and `python-dotenv`
- External dependency: `claude` CLI must be in PATH
- Slack User OAuth token (not bot token) with search/history/read scopes

## Key Design Decisions

- Uses Slack Search API (not Events API/Socket Mode) — simpler deployment, no webhook server needed
- Search buffer with TTL-based dedup handles Slack's search indexing delay
- Channel list cached and refreshed every 10 polls to reduce API calls
- Rate limiting: 0.5s between channels, 1s between search pages
- Graceful shutdown via SIGINT/SIGTERM signal handlers
