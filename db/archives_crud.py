import os
import boto3
import uuid
import json
from boto3.dynamodb.conditions import Key

REGION = os.getenv("AWS_REGION", "eu-west-1")
dynamodb = boto3.resource("dynamodb", region_name=REGION)

# Archive table names
ARCHIVED_SESSIONS_TABLE = os.getenv("ARCHIVED_SESSIONS_TABLE", "FaqBotArchivedSessions")
ARCHIVED_MESSAGES_TABLE = os.getenv("ARCHIVED_MESSAGES_TABLE", "FaqBotArchivedMessages")

archived_sessions_table = dynamodb.Table(ARCHIVED_SESSIONS_TABLE)
archived_messages_table = dynamodb.Table(ARCHIVED_MESSAGES_TABLE)

# TTL configuration
ARCHIVE_TTL_DAYS = 120  # Delete archived data after 120 days
SECONDS_PER_DAY = 86400


def generate_archive_id(email: str, session_id: str, timestamp: int) -> str:
    """Generate a unique archive ID"""
    return f"archive-{email}-{session_id}-{timestamp}"


def ttl_timestamp(days: int = ARCHIVE_TTL_DAYS) -> int:
    """Calculate TTL timestamp (Unix epoch) for DynamoDB TTL"""
    from utils.time_utils import now
    return int(now() / 1000) + (days * SECONDS_PER_DAY)


def archive_session(
    email: str,
    session_id: str,
    session_title: str,
    created_at: int,
    last_activity_at: int,
    deleted_by: str,
    messages_count: int = 0
) -> dict:
    """
    Archive a deleted session to preserve it for 120 days

    Args:
        email: Email of user who created the session
        session_id: Original session ID
        session_title: Title of the session
        created_at: Unix timestamp of session creation
        last_activity_at: Unix timestamp of last activity
        deleted_by: Email of user who initiated deletion
        messages_count: Total number of messages in session

    Returns:
        dict with archived session data
    """
    try:
        from utils.time_utils import now

        timestamp = now()
        archive_id = generate_archive_id(email, session_id, int(timestamp / 1000))
        ttl = ttl_timestamp(ARCHIVE_TTL_DAYS)

        item = {
            "archiveId": archive_id,
            "email": email.lower().strip(),
            "sessionId": session_id,
            "sessionTitle": session_title,
            "createdAt": created_at,
            "lastActivityAt": last_activity_at,
            "deletedAt": int(timestamp / 1000),
            "deletedBy": deleted_by.lower().strip(),
            "messagesCount": messages_count,
            "expiresAt": ttl
        }

        archived_sessions_table.put_item(Item=item)

        print(f"✓ Archived session: {archive_id}")
        return item

    except Exception as e:
        print(f"ERROR archiving session: {str(e)}")
        raise


def archive_message(archive_id: str, timestamp: int, role: str, content: str) -> dict:
    """
    Archive a message from a deleted session

    Args:
        archive_id: Archive ID of the parent session
        timestamp: Unix timestamp of the message
        role: Message role ("user" or "assistant")
        content: Message content

    Returns:
        dict with archived message data
    """
    try:
        ttl = ttl_timestamp(ARCHIVE_TTL_DAYS)

        item = {
            "archiveId": archive_id,
            "timestamp": timestamp,
            "role": role,
            "content": content,
            "expiresAt": ttl
        }

        archived_messages_table.put_item(Item=item)
        return item

    except Exception as e:
        print(f"ERROR archiving message: {str(e)}")
        raise


def get_archived_session(archive_id: str) -> dict:
    """Get an archived session by archiveId"""
    try:
        response = archived_sessions_table.get_item(Key={"archiveId": archive_id})
        return response.get("Item")
    except Exception as e:
        print(f"ERROR retrieving archived session: {str(e)}")
        raise


def get_archived_messages(archive_id: str) -> list:
    """Get all messages for an archived session"""
    try:
        response = archived_messages_table.query(
            KeyConditionExpression=Key("archiveId").eq(archive_id),
            ScanIndexForward=True  # oldest -> newest
        )
        return response.get("Items", [])
    except Exception as e:
        print(f"ERROR retrieving archived messages: {str(e)}")
        raise


def list_archived_sessions_for_user(email: str, limit: int = 50) -> list:
    """
    Get all archived sessions for a user, sorted by deletion time (newest first)
    Uses the email-deletedAt-index GSI for efficient querying

    Args:
        email: User's email address
        limit: Maximum number of sessions to return

    Returns:
        List of archived sessions sorted by deletedAt (descending - newest first)
    """
    try:
        email = email.lower().strip()
        response = archived_sessions_table.query(
            IndexName="email-deletedAt-index",
            KeyConditionExpression=Key("email").eq(email),
            ScanIndexForward=False,  # Descending order - newest deletions first
            Limit=limit
        )
        return response.get("Items", [])

    except Exception as e:
        print(f"ERROR listing archived sessions: {str(e)}")
        raise


def delete_archived_session(archive_id: str) -> None:
    """Manually delete an archived session (normally done by TTL)"""
    try:
        archived_sessions_table.delete_item(Key={"archiveId": archive_id})
        print(f"✓ Deleted archived session: {archive_id}")
    except Exception as e:
        print(f"ERROR deleting archived session: {str(e)}")
        raise


def delete_archived_messages(archive_id: str) -> int:
    """Manually delete all messages for an archived session (normally done by TTL)"""
    try:
        # Get all messages for this archive
        messages = get_archived_messages(archive_id)

        # Delete each message
        deleted_count = 0
        for message in messages:
            archived_messages_table.delete_item(
                Key={
                    "archiveId": archive_id,
                    "timestamp": message["timestamp"]
                }
            )
            deleted_count += 1

        print(f"✓ Deleted {deleted_count} archived messages for: {archive_id}")
        return deleted_count

    except Exception as e:
        print(f"ERROR deleting archived messages: {str(e)}")
        raise


def restore_archived_session(archive_id: str) -> dict:
    """
    Restore an archived session back to active tables
    Returns the archived session data for re-insertion to original tables
    """
    try:
        archived_session = get_archived_session(archive_id)
        if not archived_session:
            raise ValueError(f"Archived session not found: {archive_id}")

        return {
            "email": archived_session["email"],
            "sessionId": archived_session["sessionId"],
            "sessionTitle": archived_session["sessionTitle"],
            "createdAt": archived_session["createdAt"],
            "lastActivityAt": archived_session["lastActivityAt"],
            "messagesCount": archived_session["messagesCount"]
        }

    except Exception as e:
        print(f"ERROR restoring archived session: {str(e)}")
        raise