from utils.http_response import success, error
from utils.time_utils import now

from db.users_crud import get_or_create_user, get_user
from db.sessions_crud import list_sessions_for_user
from rag.rag import get_available_knowledge_bases

def handle_user_init(body):
    """Initialize user on first login - get user info and existing sessions
    NOTE: Do NOT create a session here. Sessions are created client-side (locally) and 
    persisted on the backend when the first message is sent.
    """
    email = body.get('email')
    group = body.get('group')
    
    if not email or not group:
        return error("Email and group are required", 400)
    
    timestamp = now()
    
    # Get or create user
    user = get_or_create_user(email, group, timestamp)
    print(f"User initialized: {email}, group: {group}")
    
    # Get user's existing sessions for sidebar (do NOT create a new one)
    user_sessions = list_sessions_for_user(email)
    print(f"Found {len(user_sessions)} existing sessions")
    
    return success({
        "user": {
            "email": user["email"],
            "group": user["group"],
            "lastInteractionAt": user["lastInteractionAt"]
        },
        "sessions": user_sessions,
        "isNewUser": user.get("createdAt") is None
    })

def handle_get_user_profile(body):
    """Get user profile information"""
    email = body.get('email')
    
    if not email:
        return error("Email is required", 400)
    
    user = get_user(email)
    if not user:
        return error("User not found", 404)
    
    return success({
        "user": {
            "email": user["email"],
            "group": user["group"],
            "lastInteractionAt": user["lastInteractionAt"]
        }
    })

def handle_get_knowledge_bases(body):
    """Get available knowledge bases for the user based on their groups"""
    email = body.get('email')
    user_groups = body.get('groups', [])

    if not email:
        return error("Email is required", 400)

    if not user_groups:
        return error("Groups are required", 400)

    # Ensure user_groups is a list (it might be a string if coming from query params)
    if isinstance(user_groups, str):
        user_groups = [user_groups]
    elif not isinstance(user_groups, list):
        user_groups = list(user_groups) if hasattr(user_groups, '__iter__') else []

    # Get available knowledge bases for these groups
    available_kbs = get_available_knowledge_bases(user_groups)

    # Return response even if no KBs available - frontend will handle displaying the message
    return success({
        "email": email,
        "groups": user_groups,
        "knowledgeBases": available_kbs,
        "count": len(available_kbs)
    })