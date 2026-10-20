"""
Task Assistant API Router
Status: Production
Created: November 2025

PURPOSE: AI-powered assistance for task construction using GPT-5-mini.
Helps users build scheduled tasks with canvas analysis, scheduling suggestions, and delivery recommendations.

NO HARDCODING - All agents and capabilities discovered dynamically from registries.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from openai import AsyncOpenAI
import os
import json
import re
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ===== REQUEST/RESPONSE MODELS =====

class TaskContext(BaseModel):
    """Current task canvas context"""
    currentNodes: List[Dict[str, Any]] = Field(default_factory=list)
    currentEdges: List[Dict[str, Any]] = Field(default_factory=list)
    schedule: Optional[Dict[str, Any]] = None
    delivery: Optional[Dict[str, Any]] = None


class TaskAssistantRequest(BaseModel):
    """Request model for task assistant"""
    message: str
    context: TaskContext
    session_id: Optional[str] = None


class TaskSuggestion(BaseModel):
    """Structured task suggestion with apply action"""
    type: str  # "schedule" | "delivery" | "canvas" | "validation"
    suggestion: Dict[str, Any]
    reasoning: Optional[str] = None


class TaskAssistantResponse(BaseModel):
    """Response model for task assistant"""
    message: str
    suggestions: Optional[List[TaskSuggestion]] = None


# ===== DYNAMIC DISCOVERY FUNCTIONS =====

def discover_available_agents() -> Dict[str, str]:
    """
    Dynamically discover available agents from registry.
    NO HARDCODING - reads from AGENT_REGISTRY.

    Returns:
        Dict mapping agent mode names to descriptions
    """
    agents = {}

    try:
        from core.tasks.registry import AGENT_REGISTRY

        for mode, spec in AGENT_REGISTRY.items():
            # Build description from spec
            tools_desc = f"Tools: {', '.join(spec.default_tools[:3])}" if spec.default_tools else ""
            mcp_desc = f"Data: {', '.join(spec.default_mcp_servers[:2])}" if spec.default_mcp_servers else ""

            description_parts = [
                spec.notes or "",
                tools_desc,
                mcp_desc
            ]
            description = " | ".join([p for p in description_parts if p])

            agents[mode.value] = description

        return agents

    except ImportError as e:
        logger.warning(f"Could not import agent registry: {e}")
        # Fallback with minimal agents
        return {
            "auto": "Auto-routing to appropriate specialist",
            "generalist": "General market research and data",
            "risk": "Risk metrics and portfolio optimization",
        }


def discover_task_capabilities() -> Dict[str, Any]:
    """
    Discover task scheduling and delivery capabilities.
    Returns metadata about supported frequencies, timezones, delivery channels.
    """
    return {
        "frequencies": ["once", "daily", "weekdays", "weekly", "biweekly", "monthly", "custom"],
        "delivery_channels": ["email", "slack", "teams", "saveToSentry"],
        "timezones": ["UTC", "America/New_York", "America/Chicago", "America/Los_Angeles", "Europe/London", "Asia/Tokyo"],
        "node_types": {
            "input": ["portfolio", "fileUpload", "oneDrive", "googleDrive"],
            "agent": ["agent"],
            "utility": ["merge", "distribute"],
            "output": ["pdfReport", "pptPresentation", "workbook"],
            "delivery": ["email", "slack", "teams", "saveToSentry"]
        }
    }


# ===== CANVAS ANALYSIS =====

def analyze_canvas_health(context: TaskContext) -> Dict[str, Any]:
    """
    Analyze the current canvas for common issues and improvements.
    Returns validation results and suggestions.

    Validates against MANDATORY WORKFLOW CONVENTION:
    Start (MUST) → Data/Agent → (if data) Agent → Agents (optional) → Output (optional) → Delivery (MUST, ONE) → End (MUST)
    """
    nodes = context.currentNodes
    edges = context.currentEdges

    issues = []
    suggestions = []

    # Check for start node (REQUIRED)
    start_nodes = [n for n in nodes if n.get('type') == 'start']
    if not start_nodes:
        issues.append("❌ Missing START node - required to begin workflow")
    elif len(start_nodes) > 1:
        issues.append("❌ Multiple START nodes - only one allowed")

    # Check for end node (REQUIRED)
    end_nodes = [n for n in nodes if n.get('type') == 'end']
    if not end_nodes:
        issues.append("❌ Missing END node - required to complete workflow")
    elif len(end_nodes) > 1:
        issues.append("❌ Multiple END nodes - only one allowed")

    # Check for delivery configuration (REQUIRED)
    delivery_nodes = [n for n in nodes if n.get('type') in ['email', 'slack', 'teams', 'saveToSentry']]
    distribute_nodes = [n for n in nodes if n.get('type') == 'distribute']

    if not delivery_nodes and not distribute_nodes:
        issues.append("❌ Missing DELIVERY node - must have at least one (email, Slack, Teams, Save to Sentry, or Distribute)")
    elif len(delivery_nodes) > 1 and not distribute_nodes:
        issues.append(f"❌ Multiple delivery nodes ({len(delivery_nodes)}) without Distribute - use Distribute node for multiple deliveries")

    # Check for data input nodes and validate agent follows
    data_input_nodes = [n for n in nodes if n.get('type') in ['portfolio', 'fileUpload', 'oneDrive', 'googleDrive']]
    agent_nodes = [n for n in nodes if n.get('type') == 'agent']

    if data_input_nodes:
        # Build edge map to check if data inputs connect to agents
        edge_map = {}
        for edge in edges:
            source = edge.get('source')
            target = edge.get('target')
            if source not in edge_map:
                edge_map[source] = []
            edge_map[source].append(target)

        for data_node in data_input_nodes:
            data_id = data_node.get('id')
            connected_nodes = edge_map.get(data_id, [])
            has_agent_after = any(
                nodes[i].get('type') == 'agent'
                for i in range(len(nodes))
                if nodes[i].get('id') in connected_nodes
            )
            if not has_agent_after:
                data_type = data_node.get('type', 'data')
                issues.append(f"❌ Data input '{data_type}' must connect to an AGENT node to process the data")

    # Check for disconnected nodes
    connected_ids = set()
    for edge in edges:
        connected_ids.add(edge.get('source'))
        connected_ids.add(edge.get('target'))

    disconnected = [
        n for n in nodes
        if n.get('id') not in connected_ids
        and n.get('type') not in ['start', 'end']  # Start/end might not be connected if canvas is empty
    ]
    if disconnected:
        disconnected_types = [n.get('type', 'unknown') for n in disconnected]
        issues.append(f"❌ {len(disconnected)} disconnected node(s): {', '.join(disconnected_types)}")

    # Suggestions for optional improvements
    if not agent_nodes and len(nodes) > 1:
        suggestions.append("💡 Add an AGENT node to analyze your data")

    output_nodes = [n for n in nodes if n.get('type') in ['pdfReport', 'pptPresentation', 'workbook']]
    if not output_nodes and len(nodes) > 3:
        suggestions.append("💡 Consider adding an OUTPUT node (PDF, PPT, Workbook) for professional formatting")

    if agent_nodes and len(agent_nodes) == 1 and data_input_nodes:
        suggestions.append("💡 You can chain multiple agents together for complex analysis")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "suggestions": suggestions,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "has_required_nodes": {
            "start": len(start_nodes) == 1,
            "end": len(end_nodes) == 1,
            "delivery": len(delivery_nodes) >= 1 or len(distribute_nodes) >= 1,
        },
        "has_utility_nodes": {
            "merge": len([n for n in nodes if n.get('type') == 'merge']) > 0,
            "distribute": len(distribute_nodes) > 0,
        }
    }


# ===== SCHEDULE INTELLIGENCE =====

def suggest_cron_expression(description: str) -> Optional[Dict[str, Any]]:
    """
    Suggest cron expression and schedule config based on natural language description.
    Examples:
        "every weekday at 9am" -> {"cron": "0 9 * * 1-5", "frequency": "weekdays", "time": "09:00"}
        "daily at 5pm" -> {"cron": "0 17 * * *", "frequency": "daily", "time": "17:00"}
        "first Monday of month" -> {"cron": "0 9 * * 1#1", "frequency": "custom"}
    """
    lower_desc = description.lower()

    patterns = {
        "weekday": {"cron": "0 9 * * 1-5", "frequency": "weekdays", "time": "09:00"},
        "daily": {"cron": "0 9 * * *", "frequency": "daily", "time": "09:00"},
        "monday": {"cron": "0 9 * * 1", "frequency": "weekly", "days_of_week": [1]},
        "tuesday": {"cron": "0 9 * * 2", "frequency": "weekly", "days_of_week": [2]},
        "wednesday": {"cron": "0 9 * * 3", "frequency": "weekly", "days_of_week": [3]},
        "thursday": {"cron": "0 9 * * 4", "frequency": "weekly", "days_of_week": [4]},
        "friday": {"cron": "0 17 * * 5", "frequency": "weekly", "days_of_week": [5]},
        "monthly": {"cron": "0 9 1 * *", "frequency": "monthly", "day_of_month": 1},
        "weekly": {"cron": "0 9 * * 1", "frequency": "weekly", "days_of_week": [1]},
    }

    for key, config in patterns.items():
        if key in lower_desc:
            return config

    return None


# ===== MAIN ENDPOINT =====

@router.post("/assistant", response_model=TaskAssistantResponse)
async def task_assistant(request: TaskAssistantRequest):
    """
    AI-powered task construction assistant using GPT-5-mini.

    Features:
    - Canvas analysis and validation
    - Schedule suggestions (natural language to cron)
    - Delivery channel recommendations
    - Agent suggestions based on use case
    - Dynamic capability discovery (no hardcoding)

    Returns structured suggestions with apply actions for frontend.
    """
    try:
        # Initialize OpenAI client
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Discover available agents and capabilities
        available_agents = discover_available_agents()
        task_capabilities = discover_task_capabilities()
        canvas_health = analyze_canvas_health(request.context)

        # Build canvas summary
        canvas_nodes = request.context.currentNodes or []
        canvas_edges = request.context.currentEdges or []
        schedule_config = request.context.schedule or {}
        delivery_config = request.context.delivery or {}

        if canvas_nodes:
            node_details = []
            for i, node in enumerate(canvas_nodes):
                node_type = node.get('type', 'unknown')
                node_label = node.get('data', {}).get('label', f'Node {i}')
                agent_mode = node.get('data', {}).get('agent', '')

                if node_type == 'agent' and agent_mode:
                    node_details.append(f"  [{i}] {node_type}: {agent_mode}")
                else:
                    node_details.append(f"  [{i}] {node_type}: {node_label}")

            canvas_summary = f"""Current task canvas:
{chr(10).join(node_details)}
Connections: {len(canvas_edges)} edges
Health: {'✓ Valid' if canvas_health['valid'] else '⚠ Issues found'}
{chr(10).join(['  - ' + issue for issue in canvas_health['issues']])}"""
        else:
            canvas_summary = "Canvas is empty - ready to build a new task"

        # Build schedule summary
        if schedule_config:
            freq = schedule_config.get('frequency', 'not set')
            time_val = schedule_config.get('time', 'not set')
            tz = schedule_config.get('timezone', 'UTC')
            schedule_summary = f"Schedule: {freq} at {time_val} ({tz})"
        else:
            schedule_summary = "Schedule: Not configured"

        # Build delivery summary
        if delivery_config:
            channel = delivery_config.get('primary_channel', 'not set')
            delivery_summary = f"Delivery: {channel}"
        else:
            delivery_summary = "Delivery: Not configured"

        # Build agent descriptions
        agent_descriptions = "\n".join([f"- {name}: {desc}" for name, desc in available_agents.items()])

        # Build comprehensive system prompt
        system_prompt = f"""You are the Sentry Task Assistant - an expert at building scheduled financial analysis tasks.

==== YOUR ROLE ====
Help users build automated tasks that run on schedules and deliver results via email, Slack, or Teams.
Analyze their current canvas, suggest improvements, validate configurations, and recommend schedules.

==== AVAILABLE AGENTS ====
{agent_descriptions}

==== TASK CAPABILITIES ====
SCHEDULING:
- Frequencies: {', '.join(task_capabilities['frequencies'])}
- Timezones: {', '.join(task_capabilities['timezones'])}
- Time format: HH:MM (24-hour)
- Cron expressions supported for custom frequencies

DELIVERY CHANNELS:
- Email: Send to email lists, AI-generated messages
- Slack: Post to Slack channels (requires connection)
- Teams: Post to Teams channels (requires connection)
- Save to Sentry: Store in user's workspace

NODE TYPES:
- Input: {', '.join(task_capabilities['node_types']['input'])}
- Agent: {', '.join(task_capabilities['node_types']['agent'])}
- Utility: {', '.join(task_capabilities['node_types']['utility'])} (Merge: combine multiple sources; Distribute: send to multiple deliveries)
- Output: {', '.join(task_capabilities['node_types']['output'])}
- Delivery: {', '.join(task_capabilities['node_types']['delivery'])}

==== CURRENT TASK STATE ====
{canvas_summary}
{schedule_summary}
{delivery_summary}

==== MANDATORY WORKFLOW CONVENTION ====
All task canvases MUST follow this exact flow structure:

1. START NODE (REQUIRED) - Every workflow begins here
2. DATA INPUT OR AGENT NODE (REQUIRED) - Choose one:
   - Data Input: portfolio, fileUpload, oneDrive, googleDrive
   - Agent: Direct agent analysis
3. IF DATA INPUT → AGENT NODE (REQUIRED) - Must process the data with an agent
4. ADDITIONAL AGENTS (OPTIONAL) - Can chain multiple agents: Agent 1 → Agent 2 → Agent 3
5. UTILITY NODES (OPTIONAL) - Use as needed:
   - Merge: Combine multiple data sources (e.g., Portfolio 1 + Portfolio 2 → Merge → Agent)
   - Distribute: Send to multiple delivery channels (e.g., Agent → Distribute → Email + Slack → End)
6. OUTPUT FORMATTING (OPTIONAL) - Format results: pdfReport, pptPresentation, workbook
7. DELIVERY NODE (REQUIRED) - Delivery method:
   - Single delivery: email, slack, teams, OR saveToSentry (pick ONE)
   - Multiple deliveries: Use Distribute node to send to multiple channels
8. END NODE (REQUIRED) - Every workflow ends here (can accept multiple inputs from Distribute)

VALIDATION RULES:
✅ MUST have: Start → ... → Delivery → End
✅ IF data node exists → MUST have agent after it
✅ All nodes must be connected (no orphaned nodes)
✅ Merge node: Requires 2+ inputs, 1 output to agent
✅ Distribute node: Requires 1 input, 2+ outputs to delivery nodes
✅ END node can accept multiple inputs (when using Distribute)
❌ CANNOT skip Start or End nodes
❌ CANNOT have data input without processing agent

==== RESPONSE GUIDELINES ====

FOR CANVAS QUESTIONS:
- Explain what agents are best for specific analysis types
- ALWAYS suggest sequences following the mandatory convention above
- Validate current canvas against the required flow structure
- Point out any violations of the workflow convention
- Recommend specific agents from the available list
- Suggest Merge node when: Combining multiple portfolios, multiple file sources, or data from different inputs
- Suggest Distribute node when: User wants results sent to multiple channels (email + Slack, etc.)

FOR SCHEDULING QUESTIONS:
- Suggest appropriate frequencies based on use case
- Recommend timezone based on market hours or user location
- Provide cron expressions for custom schedules
- Example: "Market open daily" → daily, 09:30, America/New_York

FOR DELIVERY QUESTIONS:
- Recommend email for reports and summaries
- Recommend Slack for alerts and quick updates
- Recommend Teams for enterprise collaboration
- Suggest AI-generated messages for professional formatting
- For multiple delivery channels: Use Distribute node (Agent → Distribute → Email + Slack + Teams → End)

FOR VALIDATION:
- Check workflow follows mandatory convention (Start → Data/Agent → ... → Delivery → End)
- Verify data inputs have processing agents
- Ensure delivery exists (single node OR Distribute with multiple deliveries)
- Validate Merge nodes: Must have 2+ inputs and connect to agent
- Validate Distribute nodes: Must have 1 input and 2+ delivery outputs
- Confirm all nodes are properly connected (no orphaned nodes)
- Validate schedule configuration completeness

CREATING SUGGESTIONS:
When you want to provide an actionable suggestion, use the create_suggestion tool with JSON containing:
- type: "schedule" | "delivery" | "canvas" | "validation"
- suggestion: The actual data to apply (varies by type)
- reasoning: Brief explanation of why this helps

EXAMPLES:

Schedule suggestion: {{"type": "schedule", "suggestion": {{"frequency": "daily", "time": "09:00", "timezone": "America/New_York"}}, "reasoning": "Daily at market open"}}

Delivery suggestion: {{"type": "delivery", "suggestion": {{"channel": "email"}}, "reasoning": "Best for detailed reports"}}

Canvas suggestion (simple): {{"type": "canvas", "suggestion": {{"addNodes": ["agent", "email", "end"]}}, "reasoning": "Completes basic workflow"}}

Canvas suggestion (complete workflow): {{"type": "canvas", "suggestion": {{"workflow": {{"name": "Portfolio Report", "nodes": [{{"type": "start", "label": "Start"}}, {{"type": "portfolio", "label": "Portfolio"}}, {{"type": "agent", "label": "Agent"}}, {{"type": "email", "label": "Email"}}, {{"type": "end", "label": "End"}}], "edges": [{{"source": 0, "target": 1}}, {{"source": 1, "target": 2}}, {{"source": 2, "target": 3}}, {{"source": 3, "target": 4}}]}}}}, "reasoning": "Complete workflow template. Please click on each node to personalize settings (agent mode, email addresses, report format, etc.)"}}

IMPORTANT:
- Call create_suggestion ONCE per response with your most important recommendation
- For workflow suggestions, ALWAYS remind users to click nodes to customize the template

PERSONALITY:
- Knowledgeable but approachable
- Focus on practical advice
- Suggest best practices for financial workflows
- Be concise but complete
- Use examples to illustrate points

Now respond to: {request.message}"""

        # Define custom tool for structured suggestions
        create_suggestion_tool = {
            "type": "custom",
            "name": "create_suggestion",
            "description": "Create a structured suggestion for the user. Call this ONCE with JSON containing: {\"type\": \"schedule|delivery|canvas|validation\", \"suggestion\": {...data...}, \"reasoning\": \"why this helps\"}",
        }

        # Call GPT-5-mini with custom tool
        result = await client.responses.create(
            model="gpt-5.1",
            input=system_prompt,
            reasoning={"effort": "minimal"},
            text={"verbosity": "low"},
            tools=[create_suggestion_tool],
        )

        # Extract response content and tool calls
        response_content = ""
        suggestions = []

        if hasattr(result, 'output_text') and result.output_text:
            response_content = result.output_text

        if hasattr(result, 'output') and result.output is not None:
            for item in result.output:
                # Check for tool calls first
                if hasattr(item, 'type') and item.type == 'custom_tool_call':
                    try:
                        tool_name = getattr(item, 'name', '')
                        if tool_name == 'create_suggestion':
                            # Extract tool input (GPT-5 sends JSON string directly)
                            tool_input = getattr(item, 'input', '')
                            if isinstance(tool_input, str) and tool_input.strip():
                                # Parse JSON string
                                suggestion_data = json.loads(tool_input)
                                if isinstance(suggestion_data, dict) and 'type' in suggestion_data and 'suggestion' in suggestion_data:
                                    suggestions.append(TaskSuggestion(**suggestion_data))
                                    logger.info(f"✅ Parsed suggestion: {suggestion_data['type']}")
                    except Exception as te:
                        logger.error(f"Failed to parse tool call: {te}")

                # Extract text content from reasoning or text items
                if hasattr(item, 'type') and item.type == 'text' and hasattr(item, 'text'):
                    response_content += item.text
                elif hasattr(item, 'content') and item.content is not None:
                    for content in item.content:
                        if hasattr(content, 'text'):
                            response_content += content.text

        # Strip any JSON from the response content (for display)
        clean_content = re.sub(r'```json\n.*?\n```', '', response_content, flags=re.DOTALL)
        clean_content = re.sub(r'\{[\s\S]*?\}', '', clean_content)
        clean_content = clean_content.strip()

        # Provide friendly message if no text content
        if not clean_content and suggestions:
            clean_content = "I've analyzed your task and created a suggestion. Click 'Apply' to add it to your canvas."
        elif not clean_content:
            logger.warning("GPT-5-mini output extraction failed")
            clean_content = "I'm having trouble processing your request. Please try rephrasing your question."

        logger.info(f"Task assistant processed query: {request.message[:50]}...")
        if suggestions:
            logger.info(f"Found {len(suggestions)} actionable suggestions")

        return TaskAssistantResponse(
            message=clean_content,
            suggestions=suggestions if suggestions else None,
        )

    except Exception as e:
        logger.error(f"Task assistant error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process task assistance: {str(e)}"
        )


@router.get("/agents")
async def get_available_task_agents():
    """
    Get list of available agents and task capabilities.
    Useful for frontend to display available options.
    """
    agents = discover_available_agents()
    capabilities = discover_task_capabilities()
    return {
        "agents": agents,
        "capabilities": capabilities
    }
