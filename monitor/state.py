import json
import logging
import os
import tempfile
import time

logger = logging.getLogger(__name__)

class State:
    def __init__(self, state_file: str, processed_id_ttl: int = 3600):
        self.state_file = state_file
        self._processed_id_ttl = processed_id_ttl
        self.channel_timestamps: dict[str, str] = {}
        self.processed_ids: dict[str, bool] = {}
        self.last_search_ts: float = 0.0
        # tracked_threads: {channel_id: {thread_ts: first_mention_ts}}
        self.tracked_threads: dict[str, dict[str, float]] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.state_file):
            logger.info("No state file found, starting fresh")
            return

        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
            self.channel_timestamps = data.get("channel_timestamps", {})
            self.last_search_ts = data.get("last_search_ts", 0.0)
            self.tracked_threads = data.get("tracked_threads", {})
            for mid in data.get("processed_ids", []):
                self.processed_ids[mid] = True
            logger.info(
                "Loaded state: %d channels, %d processed messages",
                len(self.channel_timestamps),
                len(self.processed_ids),
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load state file: %s", e)

    def save(self) -> None:
        self._evict_expired()
        data = {
            "channel_timestamps": self.channel_timestamps,
            "last_search_ts": self.last_search_ts,
            "tracked_threads": self.tracked_threads,
            "processed_ids": list(self.processed_ids.keys()),
        }
        dir_name = os.path.dirname(self.state_file) or "."
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.state_file)
            tmp_path = None  # replaced successfully, no cleanup needed
        except OSError as e:
            logger.error("Failed to save state: %s", e)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def get_oldest_ts(self, channel_id: str) -> str:
        if channel_id in self.channel_timestamps:
            return self.channel_timestamps[channel_id]
        # First time seeing this channel: use current time
        # Slack ts format is 6 decimal places
        now_ts = f"{time.time():.6f}"
        self.channel_timestamps[channel_id] = now_ts
        return now_ts

    def update_channel_ts(self, channel_id: str, ts: str) -> None:
        self.channel_timestamps[channel_id] = ts

    def get_search_cutoff_ts(self, buffer_seconds: int) -> float:
        """Return the cutoff timestamp for search, with buffer applied."""
        if self.last_search_ts == 0.0:
            return time.time() - buffer_seconds
        return self.last_search_ts - buffer_seconds

    def update_search_ts(self, ts: float) -> None:
        if ts > self.last_search_ts:
            self.last_search_ts = ts

    def track_thread(
        self, channel_id: str, thread_ts: str,
        oldest_ts: str | None = None,
    ) -> None:
        """Start or extend tracking of a thread for follow-up replies.

        If oldest_ts is provided and the thread is new, initialize its
        per-thread channel_timestamp so that _poll_tracked_threads starts
        fetching replies from that point rather than from "now".
        """
        if channel_id not in self.tracked_threads:
            self.tracked_threads[channel_id] = {}
        is_new = thread_ts not in self.tracked_threads[channel_id]
        self.tracked_threads[channel_id][thread_ts] = time.time()
        if is_new:
            # Seed the per-thread timestamp so the first poll doesn't
            # default to "now" and miss replies that arrived in between.
            if oldest_ts is not None:
                thread_key = f"{channel_id}:{thread_ts}"
                if thread_key not in self.channel_timestamps:
                    self.channel_timestamps[thread_key] = oldest_ts
            logger.info(
                "Tracking thread: channel=%s thread_ts=%s",
                channel_id,
                thread_ts,
            )
        else:
            logger.info(
                "Extended thread tracking: channel=%s thread_ts=%s",
                channel_id,
                thread_ts,
            )

    def evict_expired_threads(self, ttl_seconds: int) -> None:
        """Remove tracked threads older than TTL."""
        cutoff = time.time() - ttl_seconds
        for channel_id in list(self.tracked_threads):
            threads = self.tracked_threads[channel_id]
            expired = [
                ts for ts, tracked_at in threads.items()
                if tracked_at < cutoff
            ]
            for ts in expired:
                del threads[ts]
                # Clean up per-thread channel_timestamps entry
                thread_key = f"{channel_id}:{ts}"
                self.channel_timestamps.pop(thread_key, None)
            if not threads:
                del self.tracked_threads[channel_id]

    def is_processed(self, message_ts: str) -> bool:
        return message_ts in self.processed_ids

    def mark_processed(self, message_ts: str) -> None:
        self.processed_ids[message_ts] = True

    def _evict_expired(self) -> None:
        """Remove processed IDs older than TTL based on Slack ts."""
        cutoff = time.time() - self._processed_id_ttl
        expired = [
            ts for ts in self.processed_ids
            if float(ts) < cutoff
        ]
        for ts in expired:
            del self.processed_ids[ts]
