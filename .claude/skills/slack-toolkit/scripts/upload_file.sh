#!/bin/bash
# Upload a file to a Slack channel via files.uploadV2 API
# Usage: ./upload_file.sh <channel_id> <file_path> [initial_comment] [thread_ts]
# Requires: SLACK_USER_TOKEN environment variable

set -euo pipefail

if [ -z "${SLACK_USER_TOKEN:-}" ]; then
  echo "Error: SLACK_USER_TOKEN environment variable is not set" >&2
  exit 1
fi

if [ $# -lt 2 ]; then
  echo "Usage: $0 <channel_id> <file_path> [initial_comment] [thread_ts]" >&2
  exit 1
fi

CHANNEL="$1"
FILE_PATH="$2"
INITIAL_COMMENT="${3:-}"
THREAD_TS="${4:-}"

if [ ! -f "$FILE_PATH" ]; then
  echo "Error: File not found: ${FILE_PATH}" >&2
  exit 1
fi

FILENAME=$(basename "$FILE_PATH")
FILESIZE=$(wc -c < "$FILE_PATH" | tr -d ' ')

# Step 1: Get upload URL
UPLOAD_RESPONSE=$(curl -s -G "https://slack.com/api/files.getUploadURLExternal" \
  -H "Authorization: Bearer ${SLACK_USER_TOKEN}" \
  --data-urlencode "filename=${FILENAME}" \
  -d "length=${FILESIZE}")

OK=$(echo "$UPLOAD_RESPONSE" | jq -r '.ok')
if [ "$OK" != "true" ]; then
  ERROR=$(echo "$UPLOAD_RESPONSE" | jq -r '.error // "unknown error"')
  echo "Error: files.getUploadURLExternal failed: ${ERROR}" >&2
  exit 1
fi

UPLOAD_URL=$(echo "$UPLOAD_RESPONSE" | jq -r '.upload_url')
FILE_ID=$(echo "$UPLOAD_RESPONSE" | jq -r '.file_id')

# Step 2: Upload file content to the URL
UPLOAD_RESULT=$(curl -s -X POST "$UPLOAD_URL" \
  -F "file=@${FILE_PATH}")

# Step 3: Complete the upload and share to channel
COMPLETE_BODY=$(jq -n \
  --arg file_id "$FILE_ID" \
  --arg title "$FILENAME" \
  --arg channel_id "$CHANNEL" \
  --arg initial_comment "$INITIAL_COMMENT" \
  --arg thread_ts "$THREAD_TS" \
  '{
    files: [{id: $file_id, title: $title}],
    channel_id: $channel_id
  }
  + (if $initial_comment != "" then {initial_comment: $initial_comment} else {} end)
  + (if $thread_ts != "" then {thread_ts: $thread_ts} else {} end)')

COMPLETE_RESPONSE=$(curl -s -X POST "https://slack.com/api/files.completeUploadExternal" \
  -H "Authorization: Bearer ${SLACK_USER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "$COMPLETE_BODY")

OK=$(echo "$COMPLETE_RESPONSE" | jq -r '.ok')
if [ "$OK" != "true" ]; then
  ERROR=$(echo "$COMPLETE_RESPONSE" | jq -r '.error // "unknown error"')
  echo "Error: files.completeUploadExternal failed: ${ERROR}" >&2
  exit 1
fi

echo "$COMPLETE_RESPONSE"
