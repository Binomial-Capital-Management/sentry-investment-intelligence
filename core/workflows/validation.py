"""
Workflow Validation Logic - Simplified
Status: Production
Created: September 2025
Updated: October 2025 - Simplified for linear workflows

PURPOSE: Validates simplified workflows (Input → Agents → Output).
NO HARDCODING - validates against available agents dynamically.
KISS principle: Simple validation for simple linear structure.
"""

from typing import List, Optional, Any
import logging

from .types import (
    SimplifiedWorkflow, InputNode, AgentNode, OutputNode,
    AgentNodeType, WorkflowValidationResponse
)

logger = logging.getLogger(__name__)


class WorkflowValidator:
    """Validates simplified linear workflows"""

    # Available agents (matches langgraph_nodes.py)
    VALID_AGENTS = {
        AgentNodeType.GENERALIST,
        AgentNodeType.RISK_SPECIALIST,
        AgentNodeType.DOCUMENT_ANALYST,
        AgentNodeType.COMPARABLE_COMPANIES,
        AgentNodeType.CHART_ANALYST,
        AgentNodeType.QUANT_CODING,
        AgentNodeType.ALTERNATIVES_CODING,
        AgentNodeType.INSTITUTIONAL_ACTIVITY,
        AgentNodeType.DCF_AGENT,
        AgentNodeType.OPTIONS_CODING,
        AgentNodeType.FUNDS_PRODUCTS_ANALYST,
        AgentNodeType.PREDICTION_MARKETS_ANALYST,
    }

    def validate_simplified(self, workflow: SimplifiedWorkflow) -> WorkflowValidationResponse:
        """
        Validate a simplified workflow.

        Rules:
        1. Must have exactly 1 input node
        2. Must have at least 1 agent node
        3. Must have exactly 1 output node
        4. All agent types must be valid
        5. Custom prompts cannot be empty
        """
        errors: List[str] = []
        warnings: List[str] = []
        unknown_agents: List[str] = []

        # Input validation (already validated by Pydantic, but double-check)
        if not workflow.input_node:
            errors.append("Workflow must have an input node")

        # Agent validation
        if not workflow.agent_nodes or len(workflow.agent_nodes) == 0:
            errors.append("Workflow must have at least 1 agent node")
        else:
            # Check all agents are valid
            for idx, agent in enumerate(workflow.agent_nodes):
                if agent.agent_type not in self.VALID_AGENTS:
                    unknown_agents.append(f"{agent.agent_type} (agent {idx + 1})")
                    errors.append(f"Unknown agent type: {agent.agent_type}")

                # Check custom prompt is not empty
                if not agent.custom_prompt or not agent.custom_prompt.strip():
                    errors.append(f"Agent {idx + 1} ({agent.agent_type}): custom_prompt cannot be empty")

                # Warn if prompt doesn't use variables
                if "{input}" not in agent.custom_prompt and "{previous_output}" not in agent.custom_prompt:
                    warnings.append(
                        f"Agent {idx + 1} ({agent.agent_type}): prompt doesn't use {{input}} or {{previous_output}} variables"
                    )

        # Output validation
        if not workflow.output_node:
            errors.append("Workflow must have an output node")

        return WorkflowValidationResponse(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            agent_count=len(workflow.agent_nodes) if workflow.agent_nodes else 0,
            unknown_agents=unknown_agents
        )

    def validate_legacy(self, nodes: Optional[List[Any]], edges: Optional[List[Any]]) -> WorkflowValidationResponse:
        """
        Minimal validation for legacy format.
        Just checks that nodes/edges exist - detailed validation deferred.
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not nodes or len(nodes) == 0:
            errors.append("Legacy workflow must have at least one node")

        warnings.append("Legacy workflow format - consider migrating to simplified format")

        return WorkflowValidationResponse(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            agent_count=0,
            unknown_agents=[]
        )
