import boto3
import json
import os

# Configuration
REGION = os.environ.get("AWS_REGION", "eu-west-1")
S3_BUCKET = os.environ.get("S3_BUCKET", "redtail-documents")

s3_client = boto3.client("s3", region_name=REGION)


def extract_s3_path_from_uri(full_uri: str) -> tuple:
    """
    Extract bucket name and key from S3 URI.

    Args:
        full_uri: Full S3 URI (e.g., s3://bucket-name/path/to/file.docx)

    Returns:
        tuple: (bucket_name, key)
    """
    # Remove s3:// prefix if present
    if full_uri.startswith("s3://"):
        full_uri = full_uri[5:]

    parts = full_uri.split("/", 1)
    bucket = parts[0]
    key = parts[1] if len(parts) > 1 else ""

    return bucket, key


def get_document_folder(full_uri: str) -> str:
    """
    Extract the document folder from the S3 URI.
    For URI like s3://bucket/folder-uuid/document.docx, returns the folder-uuid part.

    Args:
        full_uri: Full S3 URI

    Returns:
        str: The folder/UUID part
    """
    bucket, key = extract_s3_path_from_uri(full_uri)
    # Get the first directory in the key
    parts = key.split("/")
    return parts[0] if parts else ""


def search_metadata_file_in_bucket(bucket: str, document_name: str) -> str:
    """
    Search the entire S3 bucket for a metadata file matching the document name.
    This is scalable and doesn't rely on knowing the directory structure.

    Args:
        bucket: S3 bucket name
        document_name: Name of the document (e.g., "document1.docx")

    Returns:
        str: S3 key of the metadata file if found, empty string otherwise
    """
    try:
        metadata_filename = f"{document_name}.metadata.json"
        print(f"Searching bucket '{bucket}' for metadata file: {metadata_filename}")

        # Use list_objects_v2 with pagination to search the entire bucket
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket)

        for page in pages:
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                key = obj["Key"]
                # Check if this object's key ends with our metadata filename
                if key.endswith(metadata_filename):
                    print(f"Found metadata file at: s3://{bucket}/{key}")
                    return key

        print(f"Metadata file '{metadata_filename}' not found in bucket '{bucket}'")
        return ""

    except Exception as e:
        print(f"ERROR searching bucket for metadata file: {str(e)}")
        return ""


def get_metadata_weburl(document_name: str, full_uri: str) -> str:
    """
    Extract webUrl from metadata.json file in S3.
    First tries the expected path, then searches the entire bucket if not found.

    Args:
        document_name: Name of the document (e.g., "document1.docx")
        full_uri: Full S3 URI of the document

    Returns:
        str: The webUrl from metadata, or empty string if not found
    """
    try:
        bucket, key = extract_s3_path_from_uri(full_uri)
        folder = get_document_folder(full_uri)

        # First, try the expected path: folder/metadata/document_name.metadata.json
        metadata_key = f"{folder}/metadata/{document_name}.metadata.json"

        print(f"Attempting to fetch metadata from s3://{bucket}/{metadata_key}")

        try:
            response = s3_client.get_object(Bucket=bucket, Key=metadata_key)
            metadata_content = response["Body"].read().decode("utf-8")
            metadata = json.loads(metadata_content)
            weburl = metadata.get("webUrl", "")
            print(f"Successfully extracted webUrl: {weburl}")
            return weburl
        except s3_client.exceptions.NoSuchKey:
            print(f"Metadata file not found at expected path: s3://{bucket}/{metadata_key}")
            print("Searching entire bucket for metadata file...")

            # Fallback: search the entire bucket for the metadata file
            found_metadata_key = search_metadata_file_in_bucket(bucket, document_name)

            if found_metadata_key:
                response = s3_client.get_object(Bucket=bucket, Key=found_metadata_key)
                metadata_content = response["Body"].read().decode("utf-8")
                metadata = json.loads(metadata_content)
                weburl = metadata.get("webUrl", "")
                print(f"Successfully extracted webUrl from found file: {weburl}")
                return weburl
            else:
                return ""

    except Exception as e:
        print(f"ERROR extracting metadata for {document_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return ""


def get_metadata_for_documents(citations: dict) -> dict:
    """
    Enrich citations with webUrl from metadata files.

    Args:
        citations: Dict of document names to page lists
                  {document_name: [page1, page2, ...], ...}

    Returns:
        dict: Enriched citations with webUrl
              {document_name: {"pages": [page1, page2, ...], "webUrl": "..."}, ...}
    """
    enriched_citations = {}

    for document_name, pages in citations.items():
        if not document_name:
            continue

        enriched_citations[document_name] = {
            "pages": pages,
            "webUrl": ""
        }

    return enriched_citations
