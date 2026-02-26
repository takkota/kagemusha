#!/bin/bash
# Add a reaction to a Slack message via Slack API
# Usage: ./add_reaction.sh <channel> <timestamp> [emoji_name]
# Requires: SLACK_USER_TOKEN environment variable

set -euo pipefail

if [ -z "${SLACK_USER_TOKEN:-}" ]; then
  echo "Error: SLACK_USER_TOKEN environment variable is not set" >&2
  exit 1
fi

if [ $# -lt 2 ]; then
  echo "Usage: $0 <channel> <timestamp> [emoji_name]" >&2
  exit 1
fi

CHANNEL="$1"
TIMESTAMP="$2"
EMOJI="${3:-eyes}"

curl -s -X POST "https://slack.com/api/reactions.add" \
  -H "Authorization: Bearer ${SLACK_USER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg channel "$CHANNEL" \
    --arg timestamp "$TIMESTAMP" \
    --arg name "$EMOJI" \
    '{channel: $channel, timestamp: $timestamp, name: $name}')"
