import logging
import signal
import sys
import time

from .config import Config, ConfigError
from .message_filter import is_relevant_dm
from .skill_invoker import invoke_skill
from .slack_client import SlackClient
from .state import State

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

_shutdown = False


def _signal_handler(signum, frame):
    global _shutdown
    logger.info("Received signal %d, shutting down...", signum)
    _shutdown = True


def run() -> None:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Load config and authenticate
    try:
        config = Config()
        config.resolve_user_id()
    except ConfigError as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)

    # TTL must exceed search buffer to prevent duplicate processing
    processed_id_ttl = max(3600, config.search_buffer_seconds * 3)
    state = State(config.state_file, processed_id_ttl=processed_id_ttl)
    slack = SlackClient(config)

    logger.info(
        "Starting Slack monitor (poll_interval=%ds, user_id=%s)",
        config.poll_interval,
        config.user_id,
    )

    while not _shutdown:
        try:
            _poll_cycle(config, slack, state)
        except Exception:
            logger.exception("Error during poll cycle")

        state.save()

        # Interruptible sleep
        for _ in range(config.poll_interval):
            if _shutdown:
                break
            time.sleep(1)

    logger.info("Shutdown complete")


def _poll_cycle(config: Config, slack: SlackClient, state: State) -> None:
    # 1. Search API for mentions (covers channels + threads)
    _search_mentions(config, slack, state)

    if _shutdown:
        return

    # 2. Poll tracked threads for follow-up replies
    # Build set of self-DM channel IDs so tracked threads in self-DMs
    # don't skip the user's own messages.
    channels = slack.get_all_channels()
    self_dm_channels = {
        ch["id"] for ch in channels
        if ch.get("is_im") and ch.get("user") == config.user_id
    }
    _poll_tracked_threads(config, slack, state, self_dm_channels)

    if _shutdown:
        return

    # 3. conversations_history for DMs only
    _poll_dms(config, slack, state, channels)


def _search_mentions(
    config: Config, slack: SlackClient, state: State
) -> None:
    cutoff_ts = state.get_search_cutoff_ts(config.search_buffer_seconds)
    matches = slack.search_mentions(config.user_id, cutoff_ts)

    max_ts = state.last_search_ts
    for match in matches:
        if _shutdown:
            break

        msg_ts = match.get("ts", "")
        if not msg_ts:
            continue

        match_ts_float = float(msg_ts)
        if match_ts_float > max_ts:
            max_ts = match_ts_float

        if state.is_processed(msg_ts):
            continue

        sender = match.get("user", match.get("username", ""))

        # Skip messages sent by ourselves via an app (skill responses)
        if match.get("app_id") and sender == config.user_id:
            state.mark_processed(msg_ts)
            continue
        channel_info = match.get("channel", {})
        channel_id = channel_info.get("id", "")
        if not channel_id:
            logger.warning(
                "Skipping match with no channel_id: ts=%s channel=%s",
                msg_ts,
                channel_info,
            )
            state.mark_processed(msg_ts)
            continue

        # Skip channels not in the configured allow-list
        if config.slack_channel_ids and channel_id not in config.slack_channel_ids:
            logger.debug(
                "Skipping mention in non-configured channel: channel=%s ts=%s",
                channel_id,
                msg_ts,
            )
            state.mark_processed(msg_ts)
            continue

        logger.info(
            "Search mention: channel=%s ts=%s user=%s",
            channel_id,
            msg_ts,
            sender,
        )
        invoke_skill(channel_id, msg_ts)
        state.mark_processed(msg_ts)

        # Track the thread for follow-up replies (only if in a thread)
        thread_ts = match.get("thread_ts")
        if thread_ts:
            state.track_thread(channel_id, thread_ts, oldest_ts=msg_ts)

    # Advance to current time so cutoff progresses even with no new messages
    state.update_search_ts(max(max_ts, time.time()))
    state.evict_expired_threads(
        config.thread_track_days * 86400
    )


def _poll_tracked_threads(
    config: Config, slack: SlackClient, state: State,
    self_dm_channels: set[str] | None = None,
) -> None:
    """Poll tracked threads for new replies (without explicit mentions)."""
    if self_dm_channels is None:
        self_dm_channels = set()

    for channel_id, threads in list(state.tracked_threads.items()):
        # Skip channels not in the configured allow-list
        if config.slack_channel_ids and channel_id not in config.slack_channel_ids:
            continue

        is_self_dm = channel_id in self_dm_channels

        for thread_ts in list(threads):
            if _shutdown:
                return

            # Use channel_timestamps to track per-thread progress
            thread_key = f"{channel_id}:{thread_ts}"
            oldest_ts = state.get_oldest_ts(thread_key)
            replies = slack.get_thread_replies(
                channel_id, thread_ts, oldest_ts
            )

            if not replies:
                continue

            replies.sort(key=lambda m: m.get("ts", "0"))

            max_ts = oldest_ts
            for msg in replies:
                msg_ts = msg.get("ts", "")
                if not msg_ts:
                    continue

                if msg_ts > max_ts:
                    max_ts = msg_ts

                if state.is_processed(msg_ts):
                    continue

                sender = msg.get("user", "")
                if sender == config.user_id and not is_self_dm:
                    state.mark_processed(msg_ts)
                    continue

                if msg.get("bot_id"):
                    state.mark_processed(msg_ts)
                    continue

                if msg.get("app_id") and sender == config.user_id:
                    state.mark_processed(msg_ts)
                    continue

                logger.info(
                    "Thread reply: channel=%s thread=%s ts=%s user=%s",
                    channel_id,
                    thread_ts,
                    msg_ts,
                    sender,
                )
                invoke_skill(channel_id, msg_ts)
                state.mark_processed(msg_ts)

            state.update_channel_ts(thread_key, max_ts)
            time.sleep(0.5)


def _poll_dms(
    config: Config, slack: SlackClient, state: State,
    channels: list[dict] | None = None,
) -> None:
    if channels is None:
        channels = slack.get_all_channels()

    for channel in channels:
        if _shutdown:
            break

        # Only process DM channels
        if not channel.get("is_im", False):
            continue

        channel_id = channel["id"]
        is_self_dm = channel.get("user") == config.user_id

        oldest_ts = state.get_oldest_ts(channel_id)
        messages = slack.get_new_messages(channel_id, oldest_ts)

        if not messages:
            continue

        # Messages are returned newest-first; process oldest-first
        messages.sort(key=lambda m: m.get("ts", "0"))

        max_ts = oldest_ts
        for msg in messages:
            msg_ts = msg.get("ts", "")
            if not msg_ts:
                continue

            if msg_ts > max_ts:
                max_ts = msg_ts

            if state.is_processed(msg_ts):
                continue

            # Skip messages containing mentions; search handles those
            mention_tag = f"<@{config.user_id}>"
            if mention_tag in msg.get("text", ""):
                continue

            if is_relevant_dm(msg, config.user_id, is_self_dm=is_self_dm):
                logger.info(
                    "DM message: channel=%s ts=%s user=%s",
                    channel_id,
                    msg_ts,
                    msg.get("user", "?"),
                )
                invoke_skill(channel_id, msg_ts)

                # Track the thread so follow-up replies are picked up
                # by _poll_tracked_threads (the skill will reply in a
                # thread rooted at msg_ts).
                thread_ts = msg.get("thread_ts", msg_ts)
                state.track_thread(channel_id, thread_ts, oldest_ts=msg_ts)

            state.mark_processed(msg_ts)

        state.update_channel_ts(channel_id, max_ts)

        time.sleep(0.5)  # Rate limit between channels


if __name__ == "__main__":
    run()
