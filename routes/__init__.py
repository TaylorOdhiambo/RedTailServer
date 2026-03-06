"""
Route handlers package for FaQBot API
"""

from .user_routes import handle_user_init, handle_get_user_profile, handle_get_knowledge_bases
from .session_routes import (
    handle_get_sessions, 
    handle_create_session, 
    handle_delete_session, 
    handle_get_session_details
)
from .messages_routes import handle_get_messages, handle_chat_message
# Define what gets imported with "from routes import *"
__all__ = [
    'handle_user_init',
    'handle_get_user_profile',
    'handle_get_knowledge_bases',
    'handle_get_sessions',
    'handle_create_session', 
    'handle_delete_session',
    'handle_get_session_details',
    'handle_get_messages',
    'handle_chat_message'
]