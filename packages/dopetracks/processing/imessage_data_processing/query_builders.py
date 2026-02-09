from typing import Optional


def build_placeholders(count: int) -> str:
    """Return a comma-separated placeholder string for parametrized queries."""
    if count <= 0:
        return "NULL"
    return ",".join(["?"] * count)


def messages_with_body_query(chat_placeholders: str) -> str:
    """
    Shared base query for pulling messages (with text/attributedBody) for a set of chats.
    Caller is responsible for providing params: [start_ts, end_ts] + chat_ids.
    """
    return f"""
        SELECT 
            message.ROWID as message_id,
            message.text,
            message.attributedBody,
            message.date,
            message.is_from_me,
            message.handle_id,
            message.associated_message_type,
            handle.id as sender_contact,
            chat.display_name as chat_name,
            chat.ROWID as chat_id,
            datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime") as date_utc
        FROM message
        JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
        JOIN chat ON chat_message_join.chat_id = chat.ROWID
        LEFT JOIN handle ON message.handle_id = handle.ROWID
        WHERE 
            message.date BETWEEN ? AND ?
            AND chat.ROWID IN ({chat_placeholders})
            AND (
                message.text IS NOT NULL 
                OR message.attributedBody IS NOT NULL
            )
            AND (
                message.associated_message_type IS NULL 
                OR message.associated_message_type = 0
            )
        ORDER BY message.date DESC
    """


_ALLOWED_ORDER_BY = {
    "last_message_date DESC",
    "last_message_date ASC",
    "message_count DESC",
    "message_count ASC",
    "member_count DESC",
    "member_count ASC",
    "chat_id ASC",
    "chat_id DESC",
}


def chat_stats_query(
    chat_placeholders: str,
    order_by: str = "last_message_date DESC",
    limit: Optional[int] = None,
) -> str:
    """
    Shared stats query for chat aggregates (message counts, member counts, last message date).
    Caller provides params: chat_ids list.
    """
    if order_by not in _ALLOWED_ORDER_BY:
        order_by = "last_message_date DESC"
    if limit is not None:
        limit = int(limit)
    limit_clause = f" LIMIT {limit}" if limit is not None else ""
    return f"""
        SELECT 
            chat.ROWID as chat_id,
            chat.display_name,
            chat.chat_identifier,
            COUNT(DISTINCT message.ROWID) as message_count,
            (
              COUNT(DISTINCT chat_handle_join.handle_id)
              + CASE WHEN SUM(CASE WHEN message.is_from_me = 1 THEN 1 ELSE 0 END) > 0 THEN 1 ELSE 0 END
            ) as member_count,
            COUNT(DISTINCT CASE WHEN message.is_from_me = 1 THEN message.ROWID END) as user_message_count,
            MAX(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as last_message_date
        FROM chat
        LEFT JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
        LEFT JOIN message ON chat_message_join.message_id = message.ROWID
        LEFT JOIN chat_handle_join ON chat.ROWID = chat_handle_join.chat_id
        WHERE chat.ROWID IN ({chat_placeholders})
        GROUP BY chat.ROWID, chat.display_name, chat.chat_identifier
        HAVING message_count > 0
        ORDER BY {order_by}
        {limit_clause}
    """

