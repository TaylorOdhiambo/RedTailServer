from db.schema import UsersTable
from boto3.dynamodb.conditions import Key

def create_user(email: str, group: str, lastInteractionAt: int):
    # Normalize email to lowercase
    email = email.lower().strip()

    item={
            "email": email,
            "group": group,
            "lastInteractionAt": lastInteractionAt
        }

    UsersTable.put_item(Item = item)
    return item

def update_last_interaction(email: str, timestamp: int):
    """
    Upserts the user's lastInteractionAt timestamp.
    Creates the user item if it doesn't exist.
    """
    # Normalize email to lowercase
    email = email.lower().strip()

    UsersTable.update_item(
        Key={"email": email},
        UpdateExpression="SET lastInteractionAt = :ts",
        ExpressionAttributeValues={":ts": int(timestamp)},
        ReturnValues="NONE"
    )

def get_user(email: str):
    # Normalize email to lowercase
    email = email.lower().strip()

    resp = UsersTable.get_item(Key={"email": email})
    return resp.get("Item")

def get_or_create_user(email: str, group: str, timestamp: int):
    """
    Get user or create if doesn't exist - IMPORTANT FOR FIRST LOGIN
    """
    # Normalize email to lowercase
    email = email.lower().strip()

    user = get_user(email)
    if not user:
        user = create_user(email, group, timestamp)
    return user