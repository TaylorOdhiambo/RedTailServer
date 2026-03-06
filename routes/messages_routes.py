from utils.http_response import success, error
from utils.time_utils import now

from db.messages_crud import save_message, get_messages, get_recent_context
from db.users_crud import update_last_interaction, get_user
from db.sessions_crud import get_session, update_session_last_activity, update_session_title

from rag.rag import rag, get_available_knowledge_bases

def handle_get_messages(body):
    """Get messages for a specific session
    Note: Local sessions (prefixed with 'local-') haven't been persisted yet,
    so we skip the session existence check for them.
    """
    session_id = body.get('sessionId')
    email = body.get('email')
    
    if not session_id:
        return error("sessionId is required", 400)
    
    # If email is provided and it's not a local session, verify session belongs to user
    if email and not session_id.startswith('local-'):
        session = get_session(email, session_id)
        if not session:
            return error("Session not found", 404)
        
        timestamp = now()
        update_last_interaction(email, timestamp)
    
    messages = get_messages(session_id)
    
    return success({
        "sessionId": session_id,
        "messages": messages,
        "count": len(messages)
    })

def handle_chat_message(body):
    """Send a message and get AI response
    Supports both local (transient) and persisted sessions.
    """
    try:
        email = body.get('email')
        user_input = body.get('userMessage', '').strip()
        session_id = body.get('sessionId')
        user_groups = body.get('userGroups', [])  # Array of groups from Cognito
        selected_group = body.get('selectedGroup')  # User's selected group
        create_session_flag = body.get('createSession', False)
        session_title = body.get('sessionTitle', 'New Chat')

        if not email or not session_id:
            return error("Email and sessionId are required", 400)

        if not user_groups or not isinstance(user_groups, list):
            return error("userGroups (array) is required", 400)

        timestamp = now()

        # Validate knowledge base access
        kb_access_denied = False
        kb_access_error_msg = ""
        selected_group_to_use = selected_group

        try:
            # Get user's actual groups from Cognito (passed in request)
            user = get_user(email)
            if not user:
                return error("User not found. Please log in again.", 404)

            # Use the groups passed from the frontend (from Cognito)
            # These are the authoritative source of the user's groups
            actual_user_groups = user_groups if user_groups else []

            # Get available knowledge bases for this user's groups
            available_kbs = get_available_knowledge_bases(actual_user_groups)

            if not available_kbs:
                kb_access_denied = True
                kb_access_error_msg = "You do not have access to any knowledge bases. Please contact your administrator to be added to a group."
                print(f"WARNING: User {email} has no KB access")
            else:
                # Validate the selected group is accessible
                if selected_group:
                    # Check if the selected group is in the user's available groups
                    if selected_group not in available_kbs:
                        kb_access_denied = True
                        kb_access_error_msg = f"You do not have access to the '{selected_group}' knowledge base. Please contact your administrator to be added to this group."
                        print(f"WARNING: User {email} tried to access unauthorized group: {selected_group}")
                    else:
                        selected_group_to_use = selected_group
                else:
                    # Use first available group if none selected
                    selected_group_to_use = list(available_kbs.keys())[0] if available_kbs else None
                    if not selected_group_to_use:
                        kb_access_denied = True
                        kb_access_error_msg = "Could not determine a knowledge base to use. Please select a group."
                        print(f"WARNING: User {email} has no default group available")

        except Exception as e:
            print(f"ERROR: Failed to validate KB access: {str(e)}")
            import traceback
            traceback.print_exc()
            return error("Failed to validate knowledge base access", 500)

        # Update user activity
        try:
            update_last_interaction(email, timestamp)
        except Exception as e:
            print(f"WARNING: Failed to update user interaction: {str(e)}")

        # Handle local session creation on first message
        if create_session_flag:
            try:
                session = get_session(email, session_id)
                if not session:
                    from db.sessions_crud import create_session
                    from utils.time_utils import ttl
                    session = create_session(
                        email=email,
                        session_id=session_id,
                        timestamp=timestamp,
                        ttl_epoch=ttl(days=60),
                        title=session_title
                    )
            except Exception as e:
                print(f"ERROR: Failed to create session: {str(e)}")
                import traceback
                traceback.print_exc()
                return error(f"Failed to create session: {str(e)}", 500)

        # Update session activity
        try:
            update_session_last_activity(email, session_id, timestamp)
        except Exception as e:
            print(f"WARNING: Failed to update session activity: {str(e)}")

        response_data = {
            "sessionId": session_id,
            "timestamp": timestamp
        }

        # Save user message if not empty
        if user_input:
            try:
                # Check if this is the first message by counting existing messages
                existing_messages = get_messages(session_id)
                is_first_message = len(existing_messages) == 0

                # Save user message
                save_message(session_id, timestamp, "user", user_input)

                # Update session title only on the first message
                if is_first_message and create_session_flag:
                    new_title = user_input[:50] + ("..." if len(user_input) > 50 else "")
                    update_session_title(email, session_id, new_title)
                    response_data["updatedTitle"] = new_title
            except Exception as e:
                print(f"ERROR: Failed to save user message: {str(e)}")
                import traceback
                traceback.print_exc()
                return error(f"Failed to save message: {str(e)}", 500)

            try:
                # Fetch conversation context (up to 3 previous exchanges)
                context_exchanges = get_recent_context(session_id, num_exchanges=3)

                # Format context as conversation history
                context_text = ""
                if context_exchanges:
                    context_text = "Previous conversation context:\n\n"
                    for idx, exchange in enumerate(context_exchanges, 1):
                        context_text += f"Q{idx}: {exchange.get('user_input', '')}\n"
                        context_text += f"A{idx}: {exchange.get('bot_response', '')}\n\n"

                # Prepend context to current query
                augmented_query = context_text + f"Current question: {user_input}" if context_text else user_input

                # Check if KB access was denied - if so, return access denied message instead of RAG
                if kb_access_denied:
                    response_text = kb_access_error_msg
                    citations = {}
                else:
                    # Generate bot response using RAG with context and selected group
                    # The group name is passed to RAG which maps it to the KB ID
                    rag_result = rag(augmented_query, selected_group_to_use)
                    response_text = rag_result["answer"]
                    citations = rag_result.get("citations", {})

                if not response_text:
                    response_text = "I apologize, but I encountered an error processing your request."

                # Format citations if available
                citations_text = ""
                if citations:
                    citations_text = "\n\n**Sources:**\n"
                    for source, citation_data in citations.items():
                        if source:
                            # Handle new citation format with pages and webUrl
                            if isinstance(citation_data, dict):
                                pages = citation_data.get("pages", [])
                                weburl = citation_data.get("webUrl", "")
                                pages_str = ", ".join(str(p) for p in pages) if pages else "N/A"
                            else:
                                # Fallback for old format
                                pages_str = ", ".join(str(p) for p in citation_data) if citation_data else "N/A"
                                weburl = ""

                            # Format citation with link if webUrl is available
                            if weburl:
                                citations_text += f"- [{source}]({weburl}) (Pages: {pages_str})\n"
                            else:
                                citations_text += f"- {source} (Pages: {pages_str})\n"

                # Append citations to response
                full_response = response_text + citations_text

                # Save bot response (with citations appended)
                save_message(session_id, timestamp + 1, "assistant", full_response)

                response_data["response"] = full_response
            except Exception as e:
                print(f"ERROR: Failed to generate or save bot response: {str(e)}")
                import traceback
                traceback.print_exc()
                # Still return an error response to user
                error_response = "I apologize, but I encountered an error processing your request."
                try:
                    save_message(session_id, timestamp + 1, "assistant", error_response)
                except Exception as save_err:
                    print(f"ERROR: Failed to save error response: {str(save_err)}")
                return error(f"Failed to process request: {str(e)}", 500)
        else:
            response_data["response"] = "Hello! How can I help you today?"

        # Return current messages for the session
        try:
            messages = get_messages(session_id)
            response_data["messages"] = messages
        except Exception as e:
            print(f"WARNING: Failed to retrieve messages: {str(e)}")
            response_data["messages"] = []

        return success(response_data)

    except Exception as e:
        print(f"CRITICAL ERROR in handle_chat_message: {str(e)}")
        import traceback
        traceback.print_exc()
        return error(f"Internal server error: {str(e)}", 500)