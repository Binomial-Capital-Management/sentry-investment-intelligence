"""
Studio API - Generate artifacts from sources
Mind maps, reports, data tables via LLM
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List, Optional, Literal, Any
import json
import logging
import re
from openai import AsyncOpenAI

from core.auth import get_clerk_auth
from core.config import get_config
from core.services.memory_service import get_memory_service
from core.services.studio_artifact_service import get_studio_artifact_service

config = get_config()
router = APIRouter(prefix="/api/v6/studio", tags=["studio"])
logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=config.openai_api_key)


class GenerateRequest(BaseModel):
    type: Literal["mindmap", "report", "datatable"]
    description: str
    format: Optional[str] = "detailed"
    sessionId: str
    sourceIds: Optional[List[str]] = None  # Specific source IDs to use
    save: Optional[bool] = True  # Whether to persist the artifact


class MindMapNode(BaseModel):
    id: str
    label: str
    children: List[str]


class MindMapResponse(BaseModel):
    title: str
    nodes: List[MindMapNode]
    sourceCount: int


class DataTableResponse(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    sourceCount: int


class ReportResponse(BaseModel):
    markdown: str
    sourceCount: int


@router.post("/generate")
async def generate_artifact(
    request: Request, payload: GenerateRequest, user=Depends(get_clerk_auth().optional_auth)
):
    """
    Generate a studio artifact (mind map, report, or data table) from sources.
    Uses the memory notebook content as context. Persists artifact to database.
    """
    clerk_user_id = getattr(request.state, "user_id", None)
    if not clerk_user_id and user:
        clerk_user_id = user.get("user_id")

    org_id = getattr(request.state, "org_id", None)

    # Get memory notes for context
    memory_service = get_memory_service()
    context = ""
    source_count = 0
    source_note_ids = []

    try:
        result = await memory_service.get_session_notes(clerk_user_id, payload.sessionId)
        notes = result.get("notes", [])

        # Filter to specific source IDs if provided
        if payload.sourceIds and len(payload.sourceIds) > 0:
            notes = [n for n in notes if n.get("id") in payload.sourceIds]

        if notes:
            source_count = len(notes)
            source_note_ids = [str(n.get("id")) for n in notes[:5] if n.get("id")]
            context = "\n\n".join(
                [
                    f"Source {i+1}: {note.get('content', '')[:2000]}"
                    for i, note in enumerate(notes[:5])  # Limit to 5 sources
                ]
            )
    except Exception as e:
        logger.warning(f"Could not load memory notes: {e}")

    # Generate the artifact
    if payload.type == "mindmap":
        result = await generate_mindmap(payload.description, context, source_count)
    elif payload.type == "report":
        result = await generate_report(
            payload.description, payload.format or "detailed", context, source_count
        )
    elif payload.type == "datatable":
        result = await generate_datatable(payload.description, context, source_count)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown type: {payload.type}")

    # Persist if requested (default True)
    if payload.save and clerk_user_id:
        artifact_service = get_studio_artifact_service()
        try:
            save_result = await artifact_service.save_artifact(
                user_id=clerk_user_id,
                session_id=payload.sessionId,
                artifact_type=payload.type,
                content=result,
                title=result.get("title") or payload.description[:100],
                description=payload.description,
                format=payload.format,
                source_note_ids=source_note_ids,
                org_id=org_id,
            )
            if save_result.get("status") == "success":
                result["id"] = str(save_result["artifact"]["id"])
                result["saved"] = True
            else:
                result["saved"] = False
                logger.warning(f"Artifact save failed: {save_result.get('message')}")
        except Exception as e:
            logger.error(f"Failed to persist artifact: {e}")
            result["saved"] = False
    else:
        result["saved"] = False

    return result


async def generate_mindmap(description: str, context: str, source_count: int) -> dict:
    """Generate a mind map structure via LLM with AI-generated queries for each node."""

    system_prompt = """You are an expert at creating clean, simple mind maps. Generate a hierarchical mind map structure as JSON.

The output MUST be valid JSON with this exact structure:
{
  "title": "Main Topic",
  "nodes": [
    {"id": "root", "label": "Main Topic: Short Title", "children": ["n1", "n2", "n3", "n4", "n5"], "query": "Give me an overview of [topic] covering all major aspects"},
    {"id": "n1", "label": "Category 1", "children": ["n1a", "n1b"], "query": "Explain [category 1] in detail. What are the key concepts, examples, and how does it relate to [main topic]?"},
    {"id": "n1a", "label": "Example: ABC", "children": [], "query": "Tell me specifically about ABC - what is it, why is it important, and what data or examples support it?"},
    {"id": "n1b", "label": "Example: XYZ", "children": [], "query": "Analyze XYZ in depth - its significance, any metrics or data points, and practical implications"},
    {"id": "n2", "label": "Category 2", "children": [], "query": "Deep dive into [category 2]. What does the source material say about this?"},
    {"id": "n3", "label": "Category 3", "children": ["n3a"], "query": "Explain [category 3] - key points, relationships, and evidence from the sources"},
    {"id": "n3a", "label": "Detail", "children": [], "query": "Focus on [detail] - what specific information is available?"},
    {"id": "n4", "label": "Category 4", "children": [], "query": "What do my sources say about [category 4]?"},
    {"id": "n5", "label": "Category 5", "children": [], "query": "Analyze [category 5] based on the pinned sources"}
  ]
}

STRICT Rules:
- The root node must have id "root"
- Create exactly 4-6 main categories from root
- Each category can have 0-3 sub-items MAX (no deeper nesting!)
- Labels must be SHORT (2-4 words max)
- Each node MUST have a "query" field with a natural question/request about that topic
- Queries should be specific and reference the actual topic, not generic placeholders
- NO deep nesting - maximum 2 levels total (root -> category -> detail)"""

    user_prompt = f"""Create a mind map about: {description}

Context from sources:
{context if context else 'No specific context provided. Create a general mind map based on the topic.'}

Return ONLY valid JSON, no markdown or explanation."""

    try:
        response = await openai_client.chat.completions.create(
            model=config.agent_model,  # Use system's GPT-5 model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        result["sourceCount"] = source_count
        result["error"] = False
        return result

    except Exception as e:
        logger.error(f"Mind map generation failed: {e}")
        # Return a basic structure on error
        return {
            "title": description[:50],
            "nodes": [
                {
                    "id": "root",
                    "label": description[:25],
                    "children": ["n1", "n2", "n3", "n4"],
                    "query": f"Give me an overview of {description}",
                },
                {
                    "id": "n1",
                    "label": "Key Concept 1",
                    "children": [],
                    "query": f"Explain the first key concept of {description}",
                },
                {
                    "id": "n2",
                    "label": "Key Concept 2",
                    "children": [],
                    "query": f"Explain the second key concept of {description}",
                },
                {
                    "id": "n3",
                    "label": "Key Concept 3",
                    "children": [],
                    "query": f"What are the important details about {description}?",
                },
                {
                    "id": "n4",
                    "label": "Key Concept 4",
                    "children": [],
                    "query": f"Summarize the main takeaways from {description}",
                },
            ],
            "sourceCount": source_count,
            "error": True,
        }


async def generate_report(description: str, format: str, context: str, source_count: int) -> dict:
    """Generate a markdown report via LLM."""

    format_instructions = {
        "briefing": "Create a brief, executive-style summary (300-500 words). Focus on key points only.",
        "detailed": "Create a comprehensive report (800-1200 words). Include analysis, evidence, and recommendations.",
        "executive": "Create an executive summary (400-600 words). Lead with conclusions, support with key data.",
    }

    system_prompt = f"""You are an expert analyst creating professional reports.

Format: {format_instructions.get(format, format_instructions['detailed'])}

Structure your report with clear markdown formatting:
- Use ## for main sections
- Use ### for subsections
- Use bullet points for lists
- Use **bold** for emphasis
- Include relevant data and metrics when available
- End with actionable conclusions or recommendations

Mermaid diagrams available. Syntax: NO `\n` or `()` in labels - use `["text"]`.

```mermaid
flowchart TD
    A["Input"] --> B{{Decision}}
    B -->|Yes| C["Success"]
    B -->|No| D["Retry"]
    style A fill:#4f46e5,color:#fff
    style C fill:#22c55e,color:#fff
    style D fill:#f59e0b,color:#000
```

Colors: `style NodeId fill:#hex,color:#text` - use for emphasis on key nodes.
Types: flowchart, sequenceDiagram, pie, gantt, mindmap, timeline, quadrantChart.
LaTeX math: $E = mc^2$ inline, $$\\sum_{{i=1}}^n x_i$$ for display."""

    user_prompt = f"""Create a {format} report about: {description}

Context from sources:
{context if context else 'No specific context provided. Create a general analysis based on the topic.'}

Generate the report in markdown format. Include Mermaid diagrams where they would help visualize key concepts, flows, or relationships."""

    try:
        response = await openai_client.chat.completions.create(
            model=config.agent_model,  # Use system's GPT-5 model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )

        return {"markdown": response.choices[0].message.content, "sourceCount": source_count, "error": False}

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return {
            "markdown": f"# {description}\n\nReport generation encountered an error. Please try again.",
            "sourceCount": source_count,
            "error": True,
        }


async def generate_datatable(description: str, context: str, source_count: int) -> dict:
    """Generate a data table via LLM."""

    system_prompt = """You are an expert at extracting and organizing data into tables.

Generate a data table as JSON with this exact structure:
{
  "columns": ["Column 1", "Column 2", "Column 3"],
  "rows": [
    ["Value 1", "Value 2", "Value 3"],
    ["Value 4", "Value 5", "Value 6"]
  ]
}

Rules:
- Create 3-6 columns based on the request
- Include 5-10 rows of data
- Use clear, descriptive column headers
- Extract real data from context when available
- Use placeholder values like "N/A" or "-" when data is unavailable
- Numbers should be formatted appropriately (e.g., "$1.2B", "15.3%")"""

    user_prompt = f"""Create a data table for: {description}

Context from sources:
{context if context else 'No specific context provided. Create a sample table structure based on the request.'}

Return ONLY valid JSON, no markdown or explanation."""

    try:
        response = await openai_client.chat.completions.create(
            model=config.agent_model,  # Use system's GPT-5 model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        result["sourceCount"] = source_count
        result["error"] = False
        return result

    except Exception as e:
        logger.error(f"Data table generation failed: {e}")
        return {
            "columns": ["Item", "Value", "Notes"],
            "rows": [["Data extraction failed", "-", "Please try again"]],
            "sourceCount": source_count,
            "error": True,
        }


# Web Search endpoint for Sources panel
class WebSearchRequest(BaseModel):
    query: str
    sessionId: str
    mode: Literal["web", "fast"] = "fast"  # fast = quick summary, web = comprehensive


class WebSearchSource(BaseModel):
    id: int
    title: str
    url: str
    snippet: str
    domain: str


class WebSearchResponse(BaseModel):
    content: str
    sources: List[WebSearchSource]
    error: bool = False


@router.post("/web-search", response_model=WebSearchResponse)
async def web_search(
    payload: WebSearchRequest, request: Request, user=Depends(get_clerk_auth().optional_auth)
):
    """Search the web and return results that can be pinned as sources."""
    from core.tools.web_search import web_search_func

    clerk_user_id = getattr(request.state, "user_id", None)
    if not clerk_user_id and user:
        clerk_user_id = getattr(user, "id", None) or getattr(user, "user_id", None)

    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        # Determine search depth based on mode
        depth = "comprehensive" if payload.mode == "web" else "brief"

        logger.info(
            f"Web search starting: query='{payload.query}', mode={payload.mode}, depth={depth}"
        )

        # Execute web search
        result = await web_search_func(query=payload.query, max_results=10, depth=depth)

        logger.info(
            f"Web search result: error={result.get('error')}, sources_count={len(result.get('sources', []))}, provider={result.get('search_provider', 'unknown')}"
        )

        if result.get("error"):
            logger.error(f"Web search error: {result.get('content')}")
            return WebSearchResponse(
                content=result.get("content", "Search failed"), sources=[], error=True
            )

        # Format sources for response
        sources = []
        raw_sources = result.get("sources", [])
        for idx, src in enumerate(raw_sources):
            try:
                source_id = src.get("id")
                # Ensure id is an integer
                if isinstance(source_id, str):
                    # Try to extract number from string id like "gemini_source_1"
                    match = re.search(r"\d+", str(source_id))
                    source_id = int(match.group()) if match else idx + 1
                elif source_id is None:
                    source_id = idx + 1

                sources.append(
                    WebSearchSource(
                        id=int(source_id),
                        title=src.get("title", "") or f"Source {idx + 1}",
                        url=src.get("url", ""),
                        snippet=src.get("snippet", ""),
                        domain=src.get("domain", ""),
                    )
                )
            except Exception as src_err:
                logger.warning(f"Failed to parse source {idx}: {src_err}, raw={src}")

        logger.info(f"Web search complete: returning {len(sources)} sources")

        return WebSearchResponse(content=result.get("content", ""), sources=sources, error=False)

    except Exception as e:
        logger.error(f"Web search failed: {e}", exc_info=True)
        return WebSearchResponse(content=f"Search failed: {str(e)}", sources=[], error=True)


# ============================================================================
# Artifact Persistence Endpoints
# ============================================================================


class ArtifactResponse(BaseModel):
    id: str
    type: str
    title: Optional[str]
    content: Any
    description: Optional[str]
    format: Optional[str]
    created_at: str
    updated_at: str


class ArtifactsListResponse(BaseModel):
    status: str
    artifacts: List[ArtifactResponse]
    total_count: int


class UpdateArtifactRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[Any] = None


@router.get("/artifacts/{session_id}")
async def get_session_artifacts(
    session_id: str,
    request: Request,
    artifact_type: Optional[str] = None,
    user=Depends(get_clerk_auth().optional_auth),
):
    """Get all artifacts for a session."""
    clerk_user_id = getattr(request.state, "user_id", None)
    if not clerk_user_id and user:
        clerk_user_id = user.get("user_id")

    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    artifact_service = get_studio_artifact_service()
    result = await artifact_service.get_session_artifacts(
        user_id=clerk_user_id, session_id=session_id, artifact_type=artifact_type
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))

    return result


@router.get("/artifact/{artifact_id}")
async def get_artifact(
    artifact_id: str, request: Request, user=Depends(get_clerk_auth().optional_auth)
):
    """Get a single artifact by ID."""
    clerk_user_id = getattr(request.state, "user_id", None)
    if not clerk_user_id and user:
        clerk_user_id = user.get("user_id")

    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    artifact_service = get_studio_artifact_service()
    result = await artifact_service.get_artifact(user_id=clerk_user_id, artifact_id=artifact_id)

    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message"))

    return result


@router.patch("/artifact/{artifact_id}")
async def update_artifact(
    artifact_id: str,
    payload: UpdateArtifactRequest,
    request: Request,
    user=Depends(get_clerk_auth().optional_auth),
):
    """Update an artifact's title or content."""
    clerk_user_id = getattr(request.state, "user_id", None)
    if not clerk_user_id and user:
        clerk_user_id = user.get("user_id")

    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    artifact_service = get_studio_artifact_service()
    result = await artifact_service.update_artifact(
        user_id=clerk_user_id, artifact_id=artifact_id, title=payload.title, content=payload.content
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))

    return result


@router.delete("/artifact/{artifact_id}")
async def delete_artifact(
    artifact_id: str, request: Request, user=Depends(get_clerk_auth().optional_auth)
):
    """Delete an artifact by ID."""
    clerk_user_id = getattr(request.state, "user_id", None)
    if not clerk_user_id and user:
        clerk_user_id = user.get("user_id")

    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    artifact_service = get_studio_artifact_service()
    result = await artifact_service.delete_artifact(user_id=clerk_user_id, artifact_id=artifact_id)

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))

    return {"status": "success", "deleted": result.get("deleted", False)}
