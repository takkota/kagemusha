import logging
import time
from datetime import datetime, timedelta, timezone

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .config import Config

logger = logging.getLogger(__name__)

CHANNEL_REFRESH_INTERVAL = 10  # refresh every 10 polls (~10 min)
SEARCH_MAX_PAGES = 5  # max pages to paginate through search results


class SlackClient:
    def __init__(self, config: Config):
        self.config = config
        self.client = WebClient(token=config.slack_user_token)
        self._channels: list[dict] = []
        self._poll_count = 0

    def get_all_channels(self) -> list[dict]:
        self._poll_count += 1

        if self._channels and self._poll_count % CHANNEL_REFRESH_INTERVAL != 0:
            return self._channels

        if self.config.slack_channel_ids:
            self._channels = self._fetch_channel_info(
                self.config.slack_channel_ids
            )
            logger.info(
                "Refreshed configured channels: %s",
                self.config.slack_channel_ids,
            )
            return self._channels

        logger.info("Fetching joined channels list...")
        channels: list[dict] = []
        cursor = None
        while True:
            try:
                resp = self.client.conversations_list(
                    types="public_channel,private_channel,mpim,im",
                    limit=200,
                    cursor=cursor or "",
                )
                channels.extend(resp.get("channels", []))
                cursor = resp.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
                time.sleep(0.5)
            except SlackApiError as e:
                logger.error("Failed to list channels: %s", e)
                break

        self._channels = channels
        logger.info("Found %d channels", len(channels))
        return self._channels

    def _fetch_channel_info(self, channel_ids: list[str]) -> list[dict]:
        channels: list[dict] = []
        for cid in channel_ids:
            try:
                resp = self.client.conversations_info(channel=cid)
                channels.append(resp["channel"])
                time.sleep(0.5)
            except SlackApiError as e:
                logger.error(
                    "Failed to get info for channel %s: %s", cid, e
                )
        return channels

    def get_new_messages(
        self, channel_id: str, oldest_ts: str
    ) -> list[dict]:
        try:
            resp = self.client.conversations_history(
                channel=channel_id,
                oldest=oldest_ts,
                limit=100,
            )
            messages = resp.get("messages", [])
            return messages
        except SlackApiError as e:
            if e.response.get("error") == "not_in_channel":
                logger.debug("Not in channel %s, skipping", channel_id)
            else:
                logger.error(
                    "Failed to fetch history for %s: %s", channel_id, e
                )
            return []

    def get_thread_replies(
        self, channel_id: str, thread_ts: str, oldest_ts: str
    ) -> list[dict]:
        """Fetch replies in a thread newer than oldest_ts."""
        try:
            resp = self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                oldest=oldest_ts,
                limit=100,
            )
            messages = resp.get("messages", [])
            # First message is the parent; exclude it
            return [m for m in messages if m.get("ts") != thread_ts]
        except SlackApiError as e:
            logger.error(
                "Failed to fetch replies for %s/%s: %s",
                channel_id,
                thread_ts,
                e,
            )
            return []

    def search_mentions(
        self, user_id: str, cutoff_ts: float
    ) -> list[dict]:
        """Search for messages mentioning the user using Search API.

        Uses date-based `after:` filter for API-level filtering,
        then applies precise timestamp cutoff in code.

        Returns matches sorted oldest-first.
        """
        # Use date 1 day before cutoff to handle timezone edge cases
        cutoff_date = datetime.fromtimestamp(cutoff_ts, tz=timezone.utc)
        after_date = (cutoff_date - timedelta(days=1)).strftime("%Y-%m-%d")

        query = f"<@{user_id}> after:{after_date}"
        all_matches: list[dict] = []
        page = 1

        while page <= SEARCH_MAX_PAGES:
            try:
                resp = self.client.search_messages(
                    query=query,
                    sort="timestamp",
                    sort_dir="desc",
                    count=20,
                    page=page,
                )
            except SlackApiError as e:
                logger.error("Search API failed: %s", e)
                break

            matches = resp.get("messages", {}).get("matches", [])
            if not matches:
                break

            # Check if we've gone past the cutoff timestamp
            reached_cutoff = False
            for match in matches:
                match_ts = float(match.get("ts", "0"))
                if match_ts < cutoff_ts:
                    reached_cutoff = True
                    break
                all_matches.append(match)

            if reached_cutoff:
                break

            paging = resp.get("messages", {}).get("paging", {})
            if page >= paging.get("pages", 1):
                break

            page += 1
            time.sleep(1)  # Rate limit for Tier 2

        # Return oldest-first for consistent processing order
        all_matches.sort(key=lambda m: float(m.get("ts", "0")))
        logger.info(
            "Search found %d new mention(s) after cutoff %.6f",
            len(all_matches),
            cutoff_ts,
        )
        return all_matches
