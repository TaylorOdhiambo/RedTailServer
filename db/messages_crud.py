from db.schema import MessagesTable
from boto3.dynamodb.conditions import Key

def save_message(session_id: str, timestamp: int, role: str, content: str):
    try:
        item = {
            "sessionId": session_id,
            "timestamp": int(timestamp),
            "role": role,
            "content": content
        }
        MessagesTable.put_item(Item=item)
        return item
    except Exception as e:
        print(f"ERROR saving message: {str(e)}")
        raise

def get_messages(session_id: str, limit: int = 100):
    try:
        resp = MessagesTable.query(
            KeyConditionExpression=Key("sessionId").eq(session_id),
            ScanIndexForward=True,   # oldest -> newest
            Limit=limit
        )
        messages = resp.get("Items", [])
        return messages
    except Exception as e:
        print(f"ERROR retrieving messages: {str(e)}")
        raise

def get_recent_context(session_id: str, num_exchanges: int = 3):
    """
    Retrieve the last N exchanges (user + assistant pairs) from a session.

    Args:
        session_id: The session ID to retrieve context from
        num_exchanges: Number of exchanges to retrieve (default: 3)

    Returns:
        A list of dicts with 'user_input' and 'bot_response' keys,
        ordered from oldest to newest. Returns empty list if no messages exist.
    """
    try:
        resp = MessagesTable.query(
            KeyConditionExpression=Key("sessionId").eq(session_id),
            ScanIndexForward=True   # oldest -> newest
        )

        messages = resp.get("Items", [])

        if not messages:
            return []

        # Build exchanges from alternating user/assistant messages
        exchanges = []
        current_exchange = {}

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")

            if role == "user":
                current_exchange["user_input"] = content
            elif role == "assistant":
                current_exchange["bot_response"] = content

            # When we have both user and assistant, add to exchanges
            if "user_input" in current_exchange and "bot_response" in current_exchange:
                exchanges.append(current_exchange)
                current_exchange = {}

        # Return the last num_exchanges exchanges
        return exchanges[-num_exchanges:] if len(exchanges) > 0 else []

    except Exception as e:
        print(f"Error retrieving context: {str(e)}")
        return []
