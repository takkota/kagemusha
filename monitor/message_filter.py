import logging

logger = logging.getLogger(__name__)

SYSTEM_SUBTYPES = {
    "channel_join",
    "channel_leave",
    "channel_topic",
    "channel_purpose",
    "channel_name",
    "channel_archive",
    "channel_unarchive",
    "group_join",
    "group_leave",
    "group_topic",
    "group_purpose",
    "group_name",
    "group_archive",
    "group_unarchive",
    "bot_message",
    "bot_add",
    "bot_remove",
    "me_message",
    "file_comment",
    "pinned_item",
    "unpinned_item",
}


def is_relevant_dm(message: dict, user_id: str, is_self_dm: bool = False) -> bool:
    """Check if a DM message should trigger the skill.

    Returns True for DM messages from someone else (non-bot, non-system).
    For self-DM channels (is_self_dm=True), also accepts messages from the user.
    Skips messages sent by ourselves via an app (skill responses).
    """
    subtype = message.get("subtype", "")
    if subtype in SYSTEM_SUBTYPES:
        return False

    sender = message.get("user", "")
    if sender == user_id and not is_self_dm:
        return False

    if message.get("bot_id"):
        return False

    if message.get("app_id") and sender == user_id:
        return False

    if sender:
        logger.debug("DM detected from %s", sender)
        return True

    return False
