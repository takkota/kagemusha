#!/bin/bash
# Download file attachments from a Slack message
# Usage: ./download_slack_files.sh <channel> <timestamp>
# Requires: SLACK_USER_TOKEN environment variable
#
# Downloads all files attached to the specified message into /tmp/slack_files/<timestamp>/
# Outputs the local file paths of downloaded files (one per line)
# Only downloads image files (image/png, image/jpeg, image/gif, image/webp, etc.)

set -euo pipefail

if [ -z "${SLACK_USER_TOKEN:-}" ]; then
  echo "Error: SLACK_USER_TOKEN environment variable is not set" >&2
  exit 1
fi

if [ $# -lt 2 ]; then
  echo "Usage: $0 <channel> <timestamp>" >&2
  exit 1
fi

CHANNEL="$1"
TIMESTAMP="$2"
DOWNLOAD_DIR="/tmp/slack_files/${TIMESTAMP}"

# Fetch the message using conversations.replies (works for both threaded and non-threaded)
RESPONSE=$(curl -s -G "https://slack.com/api/conversations.replies" \
  -H "Authorization: Bearer ${SLACK_USER_TOKEN}" \
  -d "channel=${CHANNEL}" \
  -d "ts=${TIMESTAMP}" \
  -d "limit=1" \
  -d "inclusive=true")

OK=$(echo "$RESPONSE" | jq -r '.ok')
if [ "$OK" != "true" ]; then
  # Fallback: try conversations.history for non-threaded messages
  RESPONSE=$(curl -s -G "https://slack.com/api/conversations.history" \
    -H "Authorization: Bearer ${SLACK_USER_TOKEN}" \
    -d "channel=${CHANNEL}" \
    -d "oldest=${TIMESTAMP}" \
    -d "latest=${TIMESTAMP}" \
    -d "limit=1" \
    -d "inclusive=true")

  OK=$(echo "$RESPONSE" | jq -r '.ok')
  if [ "$OK" != "true" ]; then
    ERROR=$(echo "$RESPONSE" | jq -r '.error // "unknown error"')
    echo "Error: Slack API returned error: ${ERROR}" >&2
    exit 1
  fi
fi

# Extract files array from the first message
FILES_JSON=$(echo "$RESPONSE" | jq -c '[.messages[0].files // [] | .[] | select(.mimetype | startswith("image/"))]')
FILE_COUNT=$(echo "$FILES_JSON" | jq 'length')

if [ "$FILE_COUNT" -eq 0 ]; then
  echo "No image files found in this message."
  exit 0
fi

mkdir -p "$DOWNLOAD_DIR"

echo "$FILES_JSON" | jq -c '.[]' | while read -r FILE; do
  URL=$(echo "$FILE" | jq -r '.url_private')
  NAME=$(echo "$FILE" | jq -r '.name')

  OUTPUT_PATH="${DOWNLOAD_DIR}/${NAME}"

  curl -s -L -o "$OUTPUT_PATH" \
    -H "Authorization: Bearer ${SLACK_USER_TOKEN}" \
    "$URL"

  # Verify the downloaded file is actually an image, not an HTML error page
  FILETYPE=$(file -b --mime-type "$OUTPUT_PATH")
  if echo "$FILETYPE" | grep -q '^image/'; then
    echo "$OUTPUT_PATH"
  else
    echo "Warning: ${NAME} downloaded as ${FILETYPE} instead of image (auth may have failed), skipping." >&2
    rm -f "$OUTPUT_PATH"
  fi
done
