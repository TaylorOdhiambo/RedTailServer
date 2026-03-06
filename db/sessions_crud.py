import time
from db.schema import SessionsTable, SESSION_TTL_FIELD
from boto3.dynamodb.conditions import Key

def create_session(email: str, session_id: str, timestamp: int, ttl_epoch: int, title: str):
    """
    Create a session item. TTL is an epoch timestamp in seconds.
    Removed needsTitleUpdate field.
    """
    # Normalize email to lowercase
    email = email.lower().strip()

    try:
        item = {
            "email": email,
            "sessionId": session_id,
            "createdAt": int(timestamp),
            "lastActivityAt": int(timestamp),
            "sessionTitle": title,
            SESSION_TTL_FIELD: int(ttl_epoch)
        }
        SessionsTable.put_item(Item=item)
        return item
    except Exception as e:
        print(f"ERROR creating session: {str(e)}")
        raise

def update_session_last_activity(email: str, session_id: str, timestamp: int):
    # Normalize email to lowercase
    email = email.lower().strip()

    try:
        SessionsTable.update_item(
            Key={"email": email, "sessionId": session_id},
            UpdateExpression="SET lastActivityAt = :ts",
            ExpressionAttributeValues={":ts": int(timestamp)}
        )
    except Exception as e:
        print(f"ERROR updating session activity: {str(e)}")
        raise

def update_session_title(email: str, session_id: str, new_title: str):
    """
    Update the title without needsTitleUpdate flag.
    """
    # Normalize email to lowercase
    email = email.lower().strip()

    try:
        SessionsTable.update_item(
            Key={"email": email, "sessionId": session_id},
            UpdateExpression="SET sessionTitle = :t, lastActivityAt = :ts",
            ExpressionAttributeValues={
                ":t": new_title,
                ":ts": int(time.time())
            }
        )
    except Exception as e:
        print(f"ERROR updating session title: {str(e)}")
        raise

def get_session(email: str, session_id: str):
    # Normalize email to lowercase
    email = email.lower().strip()

    try:
        resp = SessionsTable.get_item(Key={"email": email, "sessionId": session_id})
        session = resp.get("Item")
        return session
    except Exception as e:
        print(f"ERROR retrieving session: {str(e)}")
        raise

def list_sessions_for_user(email: str, limit: int = 50):
    """
    Query sessions table by email. Returns newest-first if lastActivityAt is used client-side to sort.
    """
    # Normalize email to lowercase
    email = email.lower().strip()

    try:
        resp = SessionsTable.query(
            KeyConditionExpression=Key("email").eq(email),
            ScanIndexForward=False,  # requires sort key ordering if you want newest first by SK
            Limit=limit
        )
        sessions = resp.get("Items", [])
        return sessions
    except Exception as e:
        print(f"ERROR listing sessions: {str(e)}")
        raise

def delete_session(email: str, session_id: str):
    # Normalize email to lowercase
    email = email.lower().strip()

    try:
        SessionsTable.delete_item(Key={"email": email, "sessionId": session_id})
    except Exception as e:
        print(f"ERROR deleting session: {str(e)}")
        raise