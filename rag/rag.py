import boto3
import os
import json
from rag.metadata_extraction import get_metadata_weburl

# Configuration
REGION = os.environ.get("AWS_REGION", "eu-west-1")
CC_KNOWLEDGE_BASE_ID = os.environ.get("CC_KNOWLEDGE_BASE_ID")
HR_KNOWLEDGE_BASE_ID = os.environ.get("HR_KNOWLEDGE_BASE_ID")
KQ_KNOWLEDGE_BASE_ID = os.environ.get("KQ_KNOWLEDGE_BASE_ID")

MODEL_ARN = os.environ.get("KNOWLEDGE_BASE_MODEL_ARN")

# Knowledge Base Registry - Maps user groups to their knowledge bases
KNOWLEDGE_BASE_REGISTRY = {
    "CCGroup": {
        "id": CC_KNOWLEDGE_BASE_ID,
        "name": "CC Knowledge Base"
    },
    "HRGroup": {
        "id": HR_KNOWLEDGE_BASE_ID,
        "name": "HR Knowledge Base"
    },
    "KQGroup": {
        "id": KQ_KNOWLEDGE_BASE_ID,
        "name": "KQ Knowledge Base"
    }
    # Add future KBs here — e.g. "FinanceGroup": { "id": os.environ.get("FINANCE_KNOWLEDGE_BASE_ID"), "name": "Finance Knowledge Base" }
}

bedrock_agent_runtime = boto3.client(
    service_name="bedrock-agent-runtime",
    region_name=REGION
)

bedrock_runtime = boto3.client(
    service_name="bedrock-runtime",
    region_name=REGION
)

# Dynamic fallback prompt template
FALLBACK_PROMPT_TEMPLATE = """
You are RedTail, an intelligent AI assistant created by the KQ Data team that helps KQ employees.

You are currently operating WITHOUT access to company documents.

Follow these behavioral rules strictly:

1. If the user is greeting you, thanking you, or engaging in casual conversation:
   - Respond naturally and conversationally.

2. If the user asks for factual information, company policies, procedures, data, operational details, or anything requiring knowledge:
   - Politely explain that you can only answer questions based on company documents.
   - Clearly state that you do not have information available.
   - Do NOT guess.
   - Do NOT fabricate.

3. Do NOT mention retrieval systems, references, or internal mechanisms.
4. Keep responses concise and professional.
5. Stay in character as RedTail.

User message:
"{user_query}"
"""

def get_available_knowledge_bases(user_groups: list) -> dict:
    """
    Get available knowledge bases for a user based on their groups.
    
    Args:
        user_groups: List of group names the user belongs to
    
    Returns:
        dict mapping group names to their KB info with id and name
    """
    available_kbs = {}
    
    for group in user_groups:
        if group in KNOWLEDGE_BASE_REGISTRY:
            kb_info = KNOWLEDGE_BASE_REGISTRY[group]
            # Only include if KB ID is configured
            if kb_info.get("id"):
                available_kbs[group] = kb_info
    
    return available_kbs

def select_kb(user_group: str = None):
    """
    Select the appropriate knowledge base based on group name.

    Args:
        user_group: The user's group name (e.g., "CCGroup", "HRGroup")

    Returns:
        The knowledge base ID string
    """
    # Map group name to KB ID
    if user_group and user_group in KNOWLEDGE_BASE_REGISTRY:
        kb_id = KNOWLEDGE_BASE_REGISTRY[user_group].get("id")
        if kb_id:
            return kb_id
        print(f"WARNING: Group {user_group} found but KB ID not configured")

    # Fallback to CCGroup
    return KNOWLEDGE_BASE_REGISTRY.get("CCGroup", {}).get("id")

def fallback_llm_response(query: str):
    """
    Called when RAG returns zero retrievedReferences.
    Uses LLM with dynamic persona behavior.
    """

    prompt = FALLBACK_PROMPT_TEMPLATE.format(user_query=query)

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 300,
        "temperature": 0.7
    }

    response = bedrock_runtime.invoke_model(
        modelId=MODEL_ARN,
        body=json.dumps(body)
    )

    response_body = json.loads(response["body"].read())

    return response_body["content"][0]["text"]

def rag(query, user_group="CCGroup"):
    """
    Execute RAG using Bedrock's unified retrieve_and_generate

    Args:
        query: The user query
        user_group: The user's group name (e.g., "CCGroup", "HRGroup")

    Returns:
        dict with "answer" and "citations"
    """
    try:
        kb_id_to_use = select_kb(user_group)

        if not kb_id_to_use:
            error_msg = f"Knowledge base ID not configured for {user_group}. Please contact your administrator to set up your knowledge base access."
            print(f"ERROR: {error_msg}")
            return {
                "answer": error_msg,
                "citations": {}
            }

        if not MODEL_ARN:
            error_msg = "System not properly configured. Please contact your administrator."
            print("ERROR: Model ARN not configured")
            return {
                "answer": error_msg,
                "citations": {}
            }

        response = bedrock_agent_runtime.retrieve_and_generate(
            input={"text": query},
            retrieveAndGenerateConfiguration={
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": kb_id_to_use,
                    "modelArn": MODEL_ARN
                }
            }
        )

        # Detect if any retrievedReferences exist
        retrieved_refs_exist = any(
            citation.get("retrievedReferences")
            for citation in response.get("citations", [])
        )

        # Fallback if no retrieval occurred
        if not retrieved_refs_exist:
            print("No retrievedReferences found. Falling back to LLM.")
            fallback_answer = fallback_llm_response(query)

            return {
                "answer": fallback_answer,
                "citations": {}
            }

        # Normal RAG flow
        answer = response.get("output", {}).get("text", "")

        citations_output = {}

        for citation in response.get("citations", []):
            for ref in citation.get("retrievedReferences", []):

                location = ref.get("location", {})
                metadata = ref.get("metadata", {})

                source_uri = None
                full_uri = None

                if location.get("s3Location"):
                    full_uri = location["s3Location"].get("uri")
                    if full_uri:
                        source_uri = full_uri.split("/")[-1]

                page = metadata.get(
                    "x-amz-bedrock-kb-document-page-number",
                    "N/A"
                )

                if source_uri not in citations_output:
                    citations_output[source_uri] = {
                        "pages": [],
                        "webUrl": ""
                    }

                if page not in citations_output[source_uri]["pages"]:
                    citations_output[source_uri]["pages"].append(page)

                if not citations_output[source_uri]["webUrl"] and full_uri:
                    weburl = get_metadata_weburl(source_uri, full_uri)
                    citations_output[source_uri]["webUrl"] = weburl

        return {
            "answer": answer,
            "citations": citations_output
        }

    except Exception as e:
        print(f"ERROR in rag(): {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "answer": "I encountered an error processing your request.",
            "citations": {}
        }