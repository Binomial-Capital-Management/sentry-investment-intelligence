"""
Parser for Tasks canvas payloads.
Turns raw React Flow JSON into structured TaskDefinition objects the backend can execute.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple

from .registry import (
    AVAILABLE_AGENT_MODES,
    DELIVERY_REGISTRY,
    NODE_CATEGORY_INDEX,
    NODE_REGISTRY,
    get_agent_spec,
    get_delivery_spec,
    get_node_spec,
)
from .types import (
    CanvasData,
    CanvasNode,
    TaskAgentMode,
    TaskAgentStep,
    TaskAgentSettings,
    TaskDeliveryChannel,
    TaskDeliveryStep,
    TaskDefinition,
    TaskInputSpec,
    TaskNodeType,
    TaskOutputSpec,
    TaskOutputType,
)


OUTPUT_NODE_TYPE_MAP: Dict[TaskNodeType, TaskOutputType] = {
    TaskNodeType.PDF_REPORT: TaskOutputType.PDF,
    TaskNodeType.PPT_PRESENTATION: TaskOutputType.PRESENTATION,
    TaskNodeType.WORKBOOK: TaskOutputType.WORKBOOK,
}

DELIVERY_NODE_CHANNEL_MAP: Dict[TaskNodeType, TaskDeliveryChannel] = {
    TaskNodeType.EMAIL: TaskDeliveryChannel.EMAIL,
    TaskNodeType.SLACK: TaskDeliveryChannel.SLACK,
    TaskNodeType.TEAMS: TaskDeliveryChannel.TEAMS,
    TaskNodeType.SAVE_TO_SENTRY: TaskDeliveryChannel.SAVE_TO_SENTRY,
}


class TaskParserError(ValueError):
    """Raised when the canvas payload is invalid."""


class TaskParser:
    """Parse canvas JSON into a TaskDefinition."""

    def __init__(self, canvas_data: Dict) -> None:
        self.canvas = CanvasData.parse_obj(canvas_data)
        self.nodes_by_id: Dict[str, CanvasNode] = {node.id: node for node in self.canvas.nodes}
        self.edges_by_source: Dict[str, List[str]] = defaultdict(list)
        for edge in self.canvas.edges:
            self.edges_by_source[edge.source].append(edge.target)

    def parse(self) -> TaskDefinition:
        start_node = self._ensure_single_start_node()
        self._ensure_acyclic(start_node.id)
        ordered_nodes = self._topological_order(start_node.id)

        inputs: List[TaskInputSpec] = []
        agents: List[TaskAgentStep] = []
        outputs: List[TaskOutputSpec] = []
        deliveries: List[TaskDeliveryStep] = []

        for node_id in ordered_nodes:
            node = self.nodes_by_id[node_id]
            node_type = self._coerce_node_type(node.type)
            if node_type in (TaskNodeType.START, TaskNodeType.END):
                continue

            category = NODE_CATEGORY_INDEX.get(node_type)
            if category is None:
                raise TaskParserError(f"Unknown node category for type '{node_type}'")

            if category == "input":
                inputs.append(self._to_input_spec(node, node_type))
            elif category == "agent":
                agents.append(self._to_agent_spec(node))
            elif category == "output":
                outputs.append(self._to_output_spec(node, node_type))
            elif category == "delivery":
                deliveries.append(self._to_delivery_spec(node, node_type))
            elif category == "utility":
                # Utility nodes like MERGE are pass-through nodes
                # They don't need representation in TaskDefinition
                # The executor handles data aggregation when processing upstream nodes
                continue

        return TaskDefinition(
            inputs=inputs,
            agents=agents,
            outputs=outputs,
            deliveries=deliveries,
        )

    # ===== Validation Helpers =====

    def _ensure_single_start_node(self) -> CanvasNode:
        start_nodes = [
            node for node in self.canvas.nodes if self._coerce_node_type(node.type) == TaskNodeType.START
        ]
        if not start_nodes:
            raise TaskParserError("Canvas must contain a start node")
        if len(start_nodes) > 1:
            raise TaskParserError("Canvas can only contain one start node")
        return start_nodes[0]

    def _ensure_acyclic(self, start_id: str) -> None:
        visited: Set[str] = set()
        stack: Set[str] = set()

        def dfs(node_id: str) -> None:
            visited.add(node_id)
            stack.add(node_id)
            for neighbor in self.edges_by_source.get(node_id, []):
                if neighbor not in self.nodes_by_id:
                    raise TaskParserError(f"Edge references unknown node '{neighbor}'")
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in stack:
                    raise TaskParserError("Canvas contains a cycle, which is not supported")
            stack.remove(node_id)

        dfs(start_id)

    def _topological_order(self, start_id: str) -> List[str]:
        order: List[str] = []
        visited: Set[str] = set()
        queue: deque[str] = deque([start_id])

        while queue:
            node_id = queue.popleft()
            if node_id in visited:
                continue
            visited.add(node_id)
            order.append(node_id)
            for neighbor in self.edges_by_source.get(node_id, []):
                queue.append(neighbor)

        # Ensure every non-entrance node was reachable
        missing = [
            node.id
            for node in self.canvas.nodes
            if node.id not in visited and NODE_CATEGORY_INDEX.get(self._coerce_node_type(node.type)) != "entrance"
        ]
        if missing:
            raise TaskParserError(f"One or more nodes are disconnected from the start node: {missing}")
        return order

    # ===== Conversion Helpers =====

    def _coerce_node_type(self, value: str) -> TaskNodeType:
        try:
            return TaskNodeType(value)
        except ValueError as exc:
            raise TaskParserError(f"Unsupported node type '{value}'") from exc

    def _coerce_agent_mode(self, value: str) -> TaskAgentMode:
        # Frontend defaults to "auto" when unset
        fallback = TaskAgentMode.AUTO.value
        candidate = value or fallback
        try:
            mode = TaskAgentMode(candidate)
        except ValueError as exc:
            raise TaskParserError(f"Unsupported agent mode '{candidate}'") from exc
        if mode not in AVAILABLE_AGENT_MODES:
            raise TaskParserError(f"Agent mode '{mode.value}' not configured in registry")
        return mode

    def _collect_params(self, node: CanvasNode, keys: List[str]) -> Dict:
        params = {}
        for key in keys:
            value = node.data.get(key)
            if value is not None:
                params[key] = value
        return params

    def _to_input_spec(self, node: CanvasNode, node_type: TaskNodeType) -> TaskInputSpec:
        spec = get_node_spec(node_type)
        params = self._collect_params(node, spec.config_keys)
        return TaskInputSpec(
            node_id=node.id,
            type=node_type,
            name=node.data.get("name"),
            description=node.data.get("description"),
            params=params,
        )

    def _to_agent_spec(self, node: CanvasNode) -> TaskAgentStep:
        mode_value = node.data.get("agent", TaskAgentMode.AUTO.value)
        mode = self._coerce_agent_mode(mode_value)
        agent_spec = get_agent_spec(mode)

        selected_tools = self._resolve_tools(node.data.get("tools"), agent_spec.default_tools)
        selected_mcp = self._resolve_tools(node.data.get("mcpServers"), agent_spec.default_mcp_servers)

        instructions = self._build_agent_instructions(
            node.data.get("instructions"),
            selected_tools,
            selected_mcp,
        )

        settings = TaskAgentSettings(
            reasoning=node.data.get("reasoning"),
            response_length=node.data.get("responseLength"),
            temperature=node.data.get("temperature"),
            max_output_tokens=node.data.get("maxTokens"),
            extra={
                key: value
                for key, value in node.data.items()
                if key in {"includeChatHistory", "stopSequences"} and value is not None
            },
        )

        model = node.data.get("model", agent_spec.default_model)

        return TaskAgentStep(
            node_id=node.id,
            mode=mode,
            model=model,
            tools=selected_tools,
            mcp_servers=selected_mcp,
            instructions=instructions,
            settings=settings,
        )

    def _resolve_tools(self, raw: Optional[List[str]], defaults: List[str]) -> List[str]:
        if not raw or raw == ["auto"]:
            return list(dict.fromkeys(defaults))  # preserve order, remove duplicates
        filtered = [tool for tool in raw if tool and tool != "auto"]
        if not filtered:
            return list(dict.fromkeys(defaults))
        return list(dict.fromkeys(filtered))

    def _build_agent_instructions(
        self,
        user_instructions: Optional[str],
        tools: List[str],
        mcp_servers: List[str],
    ) -> str:
        sections: List[str] = []
        if user_instructions:
            sections.append(user_instructions.strip())

        # Suggest preferred tools (not a restriction - agent can use MCP tools too)
        if tools:
            tool_line = f"Prefer using these tools when applicable: {', '.join(tools)}. You may also use MCP server tools and any other available tools as needed."
            sections.append(tool_line)
        else:
            # Auto mode: explicitly mention all tools including MCP are available
            sections.append("Use your full toolset including all MCP server tools. No tool restrictions for this task.")

        # MCP servers (if any)
        if mcp_servers:
            server_line = f"Available MCP servers: {', '.join(mcp_servers)}."
            sections.append(server_line)

        # Compliance guidance
        compliance_line = (
            "If required data or tools are missing, explain the limitation instead of fabricating results."
        )
        sections.append(compliance_line)
        return "\n".join(sections)

    def _to_output_spec(self, node: CanvasNode, node_type: TaskNodeType) -> TaskOutputSpec:
        output_type = OUTPUT_NODE_TYPE_MAP.get(node_type)
        if output_type is None:
            raise TaskParserError(f"Unsupported output node type '{node_type}'")
        spec = get_node_spec(node_type)
        params = self._collect_params(node, spec.config_keys)
        return TaskOutputSpec(
            node_id=node.id,
            type=output_type,
            name=node.data.get("name"),
            params=params,
        )

    def _to_delivery_spec(self, node: CanvasNode, node_type: TaskNodeType) -> TaskDeliveryStep:
        channel = DELIVERY_NODE_CHANNEL_MAP.get(node_type)
        if channel is None:
            raise TaskParserError(f"Unsupported delivery node type '{node_type}'")
        spec = get_node_spec(node_type)
        params = self._collect_params(node, spec.config_keys)

        if channel == TaskDeliveryChannel.EMAIL:
            recipients = params.get("emails") or []
            if not recipients:
                raise TaskParserError(f"Email node '{node.id}' must include at least one recipient")
        if channel in {TaskDeliveryChannel.SLACK, TaskDeliveryChannel.TEAMS}:
            if not node.data.get("connected"):
                raise TaskParserError(f"{channel.value} node '{node.id}' is not connected to an account")
        if channel == TaskDeliveryChannel.SLACK:
            workspace_id = params.get("workspaceId")
            channel_ids = params.get("channelIds") or []
            if isinstance(channel_ids, str):
                channel_ids = [channel_ids]
            elif not isinstance(channel_ids, list):
                channel_ids = []
            params["channelIds"] = channel_ids
            if not workspace_id:
                raise TaskParserError(f"Slack node '{node.id}' must specify a workspace")
            if not channel_ids:
                raise TaskParserError(f"Slack node '{node.id}' must specify at least one channel")
        if channel == TaskDeliveryChannel.TEAMS:
            tenant_id = params.get("tenantId")
            team_id = params.get("teamId")
            channel_ids = params.get("channelIds") or []
            if isinstance(channel_ids, str):
                channel_ids = [channel_ids]
            elif not isinstance(channel_ids, list):
                channel_ids = []
            params["channelIds"] = channel_ids
            if not tenant_id:
                raise TaskParserError(f"teams node '{node.id}' must specify a tenant")
            if not team_id:
                raise TaskParserError(f"teams node '{node.id}' must specify a team")
            if not channel_ids:
                raise TaskParserError(f"teams node '{node.id}' must specify at least one channel")

        # Validate adapter requirements
        adapter = get_delivery_spec(channel)
        for field in adapter.required_fields:
            if not params.get(field):
                raise TaskParserError(f"{channel.value} node '{node.id}' missing required field '{field}'")

        return TaskDeliveryStep(
            node_id=node.id,
            channel=channel,
            params=params,
        )


def parse_task_definition(canvas_data: Dict) -> TaskDefinition:
    """Convenience function for callers that just need the definition."""
    parser = TaskParser(canvas_data)
    return parser.parse()
