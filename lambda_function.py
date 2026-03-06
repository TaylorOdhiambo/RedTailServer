import json
import traceback

from utils import success, error
from routes import (
    handle_user_init,
    handle_get_user_profile,
    handle_get_knowledge_bases,
    handle_get_sessions,
    handle_create_session,
    handle_delete_session,
    handle_get_session_details,
    handle_get_messages,
    handle_chat_message
)

def lambda_handler(event, context):
    """
    Main Lambda router that handles all API Gateway routes
    """
    print("Received event:", json.dumps(event, indent=2))

    try:
        # Extract HTTP method and path
        http_method = event.get('httpMethod', 'POST')
        path = event.get('path', '')

        # Parse request body/query parameters
        if http_method == 'GET':
            # For GET requests, use multiValueQueryStringParameters if available (handles arrays)
            # Fall back to queryStringParameters for single values
            multi_params = event.get('multiValueQueryStringParameters', {})
            if multi_params:
                # Normalize: convert single-item arrays to strings, keep multi-item arrays as arrays
                body = {}
                for key, value in multi_params.items():
                    if isinstance(value, list):
                        body[key] = value[0] if len(value) == 1 else value
                    else:
                        body[key] = value
            else:
                body = event.get('queryStringParameters', {}) or {}
        else:
            body = parse_body(event)
        
        # Route the request
        route_handler = get_route_handler(http_method, path)
        if route_handler:
            return route_handler(body)
        else:
            return error("Route not found", 404)
            
    except Exception as e:
        print("ERROR in lambda_handler:", e)
        print(traceback.format_exc())
        return error("Internal server error: " + str(e))

def parse_body(event):
    """Parse body from API Gateway event"""
    body = event.get('body', '{}')
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}
    return body

def get_route_handler(http_method, path):
    """Route requests to appropriate handlers"""
    routes = {
        # User routes
        ('POST', '/user/init'): handle_user_init,
        ('GET', '/user/profile'): handle_get_user_profile,
        ('GET', '/user/knowledge-bases'): handle_get_knowledge_bases,
        
        # Session routes
        ('GET', '/sessions'): handle_get_sessions,
        ('POST', '/sessions'): handle_create_session,
        ('DELETE', '/sessions'): handle_delete_session,
        ('GET', '/session/details'): handle_get_session_details,
        
        # Message routes
        ('GET', '/messages'): handle_get_messages,
        ('POST', '/chat'): handle_chat_message,
    }
    
    return routes.get((http_method, path))