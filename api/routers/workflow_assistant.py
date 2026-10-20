"""
Workflow Assistant API Router
Status: Production
Created: August 2025

PURPOSE: Provides AI-powered assistance for workflow construction using GPT-5-mini.
Helps users understand agents, suggest workflows, and build analysis pipelines.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from openai import AsyncOpenAI
import os
import json
import re
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


class WorkflowContext(BaseModel):
    """Current canvas context"""
    currentNodes: List[Dict[str, str]]
    currentEdges: List[Dict[str, str]]


class WorkflowAssistantRequest(BaseModel):
    """Request model for workflow assistant"""
    message: str
    context: WorkflowContext
    session_id: Optional[str] = None


class WorkflowSuggestion(BaseModel):
    """Structured workflow suggestion"""
    name: str
    description: str
    nodes: List[Dict[str, Any]]
    edges: Optional[List[Dict[str, str]]] = None


class WorkflowAssistantResponse(BaseModel):
    """Response model for workflow assistant"""
    message: str
    suggestions: Optional[List[Dict[str, Any]]] = None


def discover_available_agents() -> Dict[str, str]:
    """
    Dynamically discover available agents and their capabilities.
    NO HARDCODING - reads from actual agent implementations.
    Returns dict of agent_name: description
    """
    agents = {}

    try:
        # Import agent nodes to check availability
        from core.ai.langgraph_nodes import (
            generalist_node,
            risk_specialist_node,
            document_analyst_node,
            comparable_companies_node,
            chart_analyst_node,
            quant_coding_node,
            alternatives_coding_node,
            institutional_activity_node,
            dcf_agent_node
        )

        # Build agent descriptions based on what's actually available
        if generalist_node:
            agents["GENERALIST"] = "Market research, web search, data synthesis, narrative reports"
        if risk_specialist_node:
            agents["RISK SPECIALIST"] = "VaR, Monte Carlo, portfolio optimization, stress testing, quantitative analysis"
        if document_analyst_node:
            agents["DOCUMENT ANALYST"] = "Extract data from PDFs, parse financial statements, analyze uploaded documents"
        if comparable_companies_node:
            agents["COMPARABLE COMPANIES"] = "Peer analysis, valuation multiples, trading comparisons"
        if chart_analyst_node:
            agents["CHART ANALYST"] = "Create interactive charts, visualizations, technical analysis"
        if quant_coding_node:
            agents["QUANT CODING"] = "Code Interpreter for custom Python analysis, data manipulation, advanced calculations"
        if alternatives_coding_node:
            agents["ALTERNATIVES CODING"] = "Crypto, forex, and commodities analysis with code execution"
        if institutional_activity_node:
            agents["INSTITUTIONAL ACTIVITY"] = "Institutional trading patterns, flow analysis, smart money tracking"
        if dcf_agent_node:
            agents["DCF AGENT"] = "Discounted cash flow valuation, intrinsic value analysis"

        return agents
    except ImportError as e:
        # Fallback if import fails
        logger.warning(f"Could not import all agent nodes: {e}, using minimal fallback")
        return {
            "GENERALIST": "General analysis and research",
            "RISK SPECIALIST": "Risk calculations and portfolio analysis",
            "DOCUMENT ANALYST": "Document processing",
            "COMPARABLE COMPANIES": "Peer valuation"
        }


def parse_workflow_suggestions(content: str) -> List[Dict[str, Any]]:
    """
    Extract structured workflow suggestions from AI response.
    Looks for JSON blocks in the response.
    """
    suggestions = []
    
    # Ensure content is a string
    if not isinstance(content, str):
        logger.warning(f"Expected string content, got {type(content)}, converting to string")
        content = str(content)
    
    # Handle empty content
    if not content:
        return suggestions
    
    # Find JSON blocks in the response
    try:
        json_blocks = re.findall(r'```json\n(.*?)\n```', content, re.DOTALL)
    except TypeError as e:
        logger.error(f"Regex error on content type {type(content)}: {e}")
        return suggestions
    
    for block in json_blocks:
        try:
            suggestion = json.loads(block)
            # Validate it has required fields
            if 'name' in suggestion and 'nodes' in suggestion:
                suggestions.append(suggestion)
        except json.JSONDecodeError:
            logger.debug(f"Failed to parse JSON block: {block[:100]}...")
            continue
    
    return suggestions


@router.post("/assistant", response_model=WorkflowAssistantResponse)
async def workflow_assistant(request: WorkflowAssistantRequest):
    """
    AI-powered workflow construction assistant using GPT-5-mini.
    Provides suggestions and explanations for building analysis workflows.
    """
    try:
        # Initialize OpenAI client for GPT-5-mini
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Dynamically discover available agents
        available_agents = discover_available_agents()
        
        # Build detailed context about current canvas
        canvas_nodes = request.context.currentNodes or []
        canvas_edges = request.context.currentEdges or []
        
        # Analyze current canvas state
        if canvas_nodes:
            node_details = []
            for i, node in enumerate(canvas_nodes):
                node_type = node.get('type', 'unknown')
                node_label = node.get('data', {}).get('label', f'Node {i}')
                node_details.append(f"  [{i}] {node_type}: {node_label}")
            
            canvas_summary = f"""Current workflow on canvas:
{chr(10).join(node_details)}
Connections: {len(canvas_edges)} edges"""
        else:
            canvas_summary = "Canvas is empty - ready for a new workflow"
        
        # Build agent descriptions dynamically
        agent_descriptions = "\n".join([f"- {name}: {desc}" for name, desc in available_agents.items()])
        
        # Combine system and user message for GPT-5-mini
        combined_prompt = f"""You are the Sentry Workflow Assistant - an expert at building financial analysis pipelines.

==== YOUR CAPABILITIES ====
AGENTS (each is a specialized AI that processes specific tasks):
{agent_descriptions}

DATA SOURCES (exact node types - use these in JSON):
• type: "dataset", label: "Portfolio Data" - User's holdings, positions, weights
• type: "dataset", label: "File Upload" - Upload Excel, CSV, PDF, or other documents
• type: "dataset", label: "User Prompt" - Custom text input for specific instructions

OUTPUT FORMATS (exact node types - use these in JSON):
• type: "output", label: "Text Output" - Plain text results
• type: "output", label: "PDF Report" - Professional institutional PDF documents
• type: "output", label: "PowerPoint" - PPT presentation slides

==== HOW WORKFLOWS WORK ====
1. Data flows LEFT to RIGHT: Data Source → Agent → Output
2. Agents can chain: Agent → Agent (e.g., Document Analyst → Risk Specialist)
3. Multiple inputs: Many data sources → One agent (e.g., Portfolio + Market → Risk Specialist)
4. Multiple outputs: One agent → Many outputs (e.g., Risk Specialist → Charts + Document)

==== WORKFLOW EXECUTION ====
• Click "Deploy" button to execute the workflow
• Real-time status updates via HTTP polling (500ms intervals)
• Browser notifications when workflow completes or fails
• Can minimize to background while workflow runs
• View results in Results tab when complete
• Execution happens node-by-node: Input → Agent → Output
• Each node shows progress indicator during execution

==== CURRENT CANVAS ====
{canvas_summary}

==== COMMON WORKFLOW PATTERNS ====

RISK ANALYSIS:
"Start with Portfolio Data and Market Data, connect both to Risk Specialist. The Risk Specialist calculates VaR, runs Monte Carlo simulations, and stress tests. Connect it to Charts for risk visualizations and Document for a detailed report."

DOCUMENT PROCESSING:
"Upload your document as Custom Upload, connect it to Document Analyst to extract data. Then connect Document Analyst to Generalist to create a summary, and finally to Document for a formatted report."

PEER COMPARISON:
"Connect Market Data to Comparable Companies Analyst to find peers and calculate multiples. Then connect to Charts to visualize the comparison."

COMPREHENSIVE ANALYSIS:
"Chain multiple agents: Market Data → Comparable Companies Analyst → Generalist → Document. This finds peers, analyzes them, creates narrative insights, then produces a report."

==== WORKFLOW DESIGN PHILOSOPHY ====
KEEP IT SIMPLE:
• Prefer 2-3 node workflows over complex chains
• Single agent workflows are often best: Data → Agent → Output
• Only suggest multi-agent chains when truly necessary
• Don't over-engineer - users can always add more nodes later
• Example: Portfolio → Risk Specialist → PDF (simple, effective)
• Avoid: Portfolio → Document Analyst → Risk Specialist → Generalist → Charts → PDF (too complex)

SIMPLE WORKFLOW EXAMPLES:
• Risk analysis: Portfolio Data → RISK SPECIALIST → PDF Report
• Document review: File Upload → DOCUMENT ANALYST → Text Output
• Peer comparison: User Prompt → COMPARABLE COMPANIES → Charts

==== RESPONSE GUIDELINES ====

FOR GENERAL QUESTIONS:
- Explain in plain English what connects to what and why
- Mention specific outputs: "This will give you VaR charts and a risk report"
- Be specific: "The Risk Specialist needs both Portfolio and Market Data to calculate correlations"

FOR CANVAS WITH EXISTING NODES:
- Acknowledge what's there: "I see you have Portfolio Data connected to Generalist"
- Suggest next steps: "Add Market Data and connect both to Risk Specialist for risk metrics"
- Warn about issues: "Risk Specialist needs Market Data too - it can't calculate VaR with just Portfolio Data"

FOR "HOW TO" QUESTIONS:
- Give step-by-step: "First add Portfolio Data, then add Risk Specialist, connect them, then add Charts"
- Explain the why: "Risk Specialist needs portfolio positions to calculate exposure"

WORKFLOW SUGGESTIONS - ALWAYS INCLUDE JSON:
When users ask to "build", "create", "add", "construct" workflows or describe what they want:
1. First explain in plain language what you'll create
2. ALWAYS include a JSON block at the end (it will be hidden but enables the Apply button)
3. Format your response exactly like this:

I'll create a [workflow type] for you. [Explain what it does].

Then add a JSON code block with this structure:
```json
{{
  "name": "Workflow Name",
  "description": "Short description",
  "nodes": [
    {{"type": "dataset", "label": "Portfolio Data"}},
    {{"type": "agent", "label": "RISK SPECIALIST"}},
    {{"type": "output", "label": "PDF Report"}}
  ],
  "edges": [
    {{"source": "0", "target": "1"}},
    {{"source": "1", "target": "2"}}
  ]
}}
```

IMPORTANT AGENT NAMES (use exact capitalization):
- GENERALIST
- RISK SPECIALIST
- DOCUMENT ANALYST
- COMPARABLE COMPANIES
- CHART ANALYST
- QUANT CODING
- ALTERNATIVES CODING
- INSTITUTIONAL ACTIVITY
- DCF AGENT

IMPORTANT DATA SOURCE LABELS (use exact text):
- Portfolio Data
- File Upload
- User Prompt

IMPORTANT OUTPUT LABELS (use exact text):
- Text Output
- PDF Report
- PowerPoint

IMPORTANT: The JSON will be automatically hidden from the user but creates an Apply button

==== PERSONALITY ====
- You are knowledgeable but approachable
- Give practical advice, not theory
- Focus on what the user is trying to achieve
- Be concise but complete

Now respond to: {request.message}"""
        
        # Use GPT-5-mini with Responses API (optimized for speed)
        result = await client.responses.create(
            model="gpt-5.1",
            input=combined_prompt,
            reasoning={"effort": "minimal"},  # Minimal reasoning for fastest responses
            text={"verbosity": "low"},  # Short responses for speed
        )
        
        # GPT-5-mini has a known bug where output_text is empty (GitHub issue #2546)
        # We need to parse the output array instead
        response_content = ""
        
        # Try the standard output_text first
        if hasattr(result, 'output_text') and result.output_text:
            response_content = result.output_text
        
        # If empty (which it will be for GPT-5-mini), parse the output array
        if not response_content and hasattr(result, 'output'):
            for item in result.output:
                if hasattr(item, 'content'):
                    # item.content is a list of ResponseOutputText objects
                    for content in item.content:
                        if hasattr(content, 'text'):
                            response_content = content.text
                            break
                    if response_content:
                        break
        
        # Final fallback
        if not response_content:
            logger.warning("GPT-5-mini output_text bug - could not extract text")
            response_content = "Unable to process request due to GPT-5-mini output bug."
        
        # Debug logging
        logger.info(f"Response content type: {type(response_content)}, length: {len(response_content) if response_content else 0}")
        
        # Parse any workflow suggestions from the response
        suggestions = parse_workflow_suggestions(response_content)
        
        # Log for debugging
        logger.info(f"Workflow assistant processed query: {request.message[:50]}...")
        if suggestions:
            logger.info(f"Found {len(suggestions)} workflow suggestions")
        
        return WorkflowAssistantResponse(
            message=response_content,
            suggestions=suggestions if suggestions else None
        )
        
    except Exception as e:
        logger.error(f"Workflow assistant error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process workflow assistance: {str(e)}"
        )


@router.get("/agents")
async def get_available_agents():
    """Get list of available agents for the frontend"""
    agents = discover_available_agents()
    return {"agents": agents}