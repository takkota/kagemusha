import os
import logging

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    pass


class Config:
    def __init__(self):
        load_dotenv()

        self.slack_user_token: str = self._require("SLACK_USER_TOKEN")
        self.slack_user_name: str = self._require("SLACK_USER_NAME")

        channel_ids_raw = os.getenv("SLACK_CHANNEL_IDS", "")
        self.slack_channel_ids: list[str] = (
            [c.strip() for c in channel_ids_raw.split(",") if c.strip()]
            if channel_ids_raw
            else []
        )

        self.poll_interval: int = int(os.getenv("POLL_INTERVAL", "60"))
        self.search_buffer_seconds: int = int(
            os.getenv("SEARCH_BUFFER_SECONDS", "180")
        )
        self.thread_track_days: int = int(
            os.getenv("THREAD_TRACK_DAYS", "5")
        )
        self.state_file: str = os.getenv(
            "STATE_FILE", ".slack_monitor_state.json"
        )

        self.user_id: str = ""

    def _require(self, key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise ConfigError(
                f"Required environment variable {key} is not set"
            )
        return value

    def resolve_user_id(self) -> None:
        client = WebClient(token=self.slack_user_token)
        try:
            response = client.auth_test()
        except SlackApiError as e:
            raise ConfigError(
                f"Failed to authenticate with Slack: {e}"
            ) from e
        self.user_id = response["user_id"]
        logger.info(
            "Authenticated as user_id=%s (user=%s)",
            self.user_id,
            response.get("user"),
        )
