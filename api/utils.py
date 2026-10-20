import uuid
from typing import Optional, Dict
from core.config import get_config

config = get_config()

def resolve_session_id(request_body_session_id: Optional[str], request_headers: Dict[str, str], query_params: Optional[Dict[str, str]] = None) -> str:
    # Priority: body -> header -> query param -> generate new
    if request_body_session_id:
        return request_body_session_id

    header_value = request_headers.get(config.session_id_header)
    if header_value:
        return header_value

    if query_params:
        query_session_id = query_params.get('session_id')
        if query_session_id:
            return query_session_id

    return str(uuid.uuid4())

def is_recall_query(message: str) -> bool:
    recall_patterns = [
        "what did i say",
        "what did i ask",
        "my previous message",
        "my last message",
        "previous question",
        "last question",
        "what was my",
    ]
    msg_lower = message.lower()
    return any(pattern in msg_lower for pattern in recall_patterns)
