"""
Database operations package for FaQBot
"""
from .messages_crud import save_message, get_messages
from .sessions_crud import (
    create_session, 
    get_session, 
    update_session_last_activity, 
    update_session_title,
    list_sessions_for_user,
    delete_session
)
from .users_crud import get_user, create_user, update_last_interaction, get_or_create_user
from .schema import UsersTable, SessionsTable, MessagesTable, SESSION_TTL_FIELD

# Define what gets imported with "from db import *"
__all__ = [
    'save_message', 'get_messages',
    'create_session', 'get_session', 'update_session_last_activity', 
    'update_session_title', 'list_sessions_for_user', 'delete_session',
    'get_user', 'create_user', 'update_last_interaction', 'get_or_create_user',
    'UsersTable', 'SessionsTable', 'MessagesTable', 'SESSION_TTL_FIELD'
]