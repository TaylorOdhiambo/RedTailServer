from utils.http_response import success, error
from utils.time_utils import now, ttl
from utils.id_utils import new_session_id

from db.sessions_crud import create_session, list_sessions_for_user, delete_session, get_session
from db.messages_crud import get_messages
from db.users_crud import update_last_interaction
from db.archives_crud import archive_session, archive_message

def handle_get_sessions(body):
    """Get all sessions for a user"""
    email = body.get('email')

    if not email:
        return error("Email is required", 400)

    timestamp = now()
    update_last_interaction(email, timestamp)

    sessions = list_sessions_for_user(email)
    return success({
        "sessions": sessions,
        "count": len(sessions)
    })

def handle_create_session(body):
    """Create a new session"""
    email = body.get('email')
    title = body.get('title', 'New Chat')

    if not email:
        return error("Email is required", 400)

    timestamp = now()
    update_last_interaction(email, timestamp)

    session_id = new_session_id()
    session = create_session(
        email=email,
        session_id=session_id,
        timestamp=timestamp,
        ttl_epoch=ttl(days=60),
        title=title
    )

    return success({
        "session": {
            "sessionId": session["sessionId"],
            "title": session["sessionTitle"],
            "createdAt": session["createdAt"],
            "lastActivityAt": session["lastActivityAt"]
        },
        "message": "New session created successfully"
    })

def handle_delete_session(body):
    """
    Delete a session with soft-delete to archive table

    Process:
    1. Verify session exists and belongs to user
    2. Get all messages from the session
    3. Archive the session to FaqBotArchivedSessions
    4. Archive all messages to FaqBotArchivedMessages
    5. Delete session from FaqBotSessions
    6. Archive entries will auto-delete after 120 days via TTL
    """
    email = body.get('email')
    session_id = body.get('sessionId')

    if not email or not session_id:
        return error("Email and sessionId are required", 400)

    timestamp = now()
    update_last_interaction(email, timestamp)

    try:
        # Verify session belongs to user
        session = get_session(email, session_id)
        if not session:
            return error("Session not found", 404)

        # Get all messages for this session
        messages = get_messages(session_id)

        # Archive the session with metadata
        archive_id = archive_session(
            email=email,
            session_id=session_id,
            session_title=session.get("sessionTitle", "Untitled"),
            created_at=session.get("createdAt"),
            last_activity_at=session.get("lastActivityAt"),
            deleted_by=email,  # User who initiated deletion
            messages_count=len(messages)
        )

        # Archive all messages associated with this session
        archived_message_count = 0
        for message in messages:
            try:
                archive_message(
                    archive_id=archive_id["archiveId"],
                    timestamp=message.get("timestamp"),
                    role=message.get("role"),
                    content=message.get("content")
                )
                archived_message_count += 1
            except Exception as e:
                print(f"WARNING: Failed to archive message from session {session_id}: {str(e)}")
                # Continue with next message if one fails

        # Delete session from active table
        delete_session(email, session_id)

        print(f"✓ Session deleted and archived: {session_id} ({archived_message_count} messages)")

        return success({
            "message": "Session deleted successfully",
            "deletedSessionId": session_id,
            "archivedMessages": archived_message_count,
            "archiveId": archive_id["archiveId"],
            "expiresAt": archive_id["expiresAt"]  # When it will be auto-deleted
        })

    except Exception as e:
        print(f"ERROR in handle_delete_session: {str(e)}")
        import traceback
        traceback.print_exc()
        return error(f"Failed to delete session: {str(e)}", 500)

def handle_get_session_details(body):
    """Get detailed information about a specific session"""
    email = body.get('email')
    session_id = body.get('sessionId')

    if not email or not session_id:
        return error("Email and sessionId are required", 400)

    session = get_session(email, session_id)
    if not session:
        return error("Session not found", 404)

    update_last_interaction(email, now())

    return success({
        "session": session
    })