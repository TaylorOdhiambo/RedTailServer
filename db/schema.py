import os
import boto3

REGION = os.getenv("AWS_REGION", "eu-west-1")

dynamodb = boto3.resource("dynamodb", region_name=REGION)

# Table names - change if your actual table names differ
USERS_TABLE = os.getenv("USERS_TABLE", "FaqBotUsers")
SESSIONS_TABLE = os.getenv("SESSIONS_TABLE", "FaqBotSessions")
MESSAGES_TABLE = os.getenv("MESSAGES_TABLE", "FaqBotMessages")

# Archive table names - for soft-deleted sessions and messages
ARCHIVED_SESSIONS_TABLE = os.getenv("ARCHIVED_SESSIONS_TABLE", "FaqBotArchivedSessions")
ARCHIVED_MESSAGES_TABLE = os.getenv("ARCHIVED_MESSAGES_TABLE", "FaqBotArchivedMessages")

# TTL attribute name for sessions (Unix epoch seconds)
SESSION_TTL_FIELD = "expiresAt"
ARCHIVE_TTL_FIELD = "expiresAt"

# Table objects
UsersTable = dynamodb.Table(USERS_TABLE)
SessionsTable = dynamodb.Table(SESSIONS_TABLE)
MessagesTable = dynamodb.Table(MESSAGES_TABLE)

# Archive table objects
ArchivedSessionsTable = dynamodb.Table(ARCHIVED_SESSIONS_TABLE)
ArchivedMessagesTable = dynamodb.Table(ARCHIVED_MESSAGES_TABLE)