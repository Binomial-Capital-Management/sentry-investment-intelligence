"""
Task Canvas Validation Microservice
Validates workflow structure, node configurations, and logical flow.
NO HARDCODING - Uses registry for dynamic validation.
"""

from typing import Dict, Any, List, Optional, Set, Tuple
from enum import Enum
import logging

from core.tasks.registry import (
    AGENT_REGISTRY,
    NODE_REGISTRY,
    DELIVERY_REGISTRY,
    NODE_CATEGORY_INDEX,
)
from core.tasks.types import TaskNodeType

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    ERROR = "error"      # Blocks execution
    WARNING = "warning"  # May cause issues
    INFO = "info"        # Suggestions for improvement


class ValidationIssue:
    """Single validation issue with context."""
    
    def __init__(
        self,
        severity: ValidationSeverity,
        message: str,
        node_id: Optional[str] = None,
        category: str = "general"
    ):
        self.severity = severity
        self.message = message
        self.node_id = node_id
        self.category = category
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "message": self.message,
            "node_id": self.node_id,
            "category": self.category,
        }


class CanvasValidator:
    """Validates task canvas structure and configuration."""
    
    def __init__(self, canvas_data: Dict[str, Any]):
        self.nodes = canvas_data.get("nodes", [])
        self.edges = canvas_data.get("edges", [])
        self.issues: List[ValidationIssue] = []
        self.invalid_nodes: Set[str] = set()  # Track nodes with structural issues
        
        # Build lookup structures
        self.nodes_by_id = {n["id"]: n for n in self.nodes}
        self.edges_by_source = {}
        self.edges_by_target = {}
        
        for edge in self.edges:
            source = edge["source"]
            target = edge["target"]
            
            if source not in self.edges_by_source:
                self.edges_by_source[source] = []
            self.edges_by_source[source].append(target)
            
            if target not in self.edges_by_target:
                self.edges_by_target[target] = []
            self.edges_by_target[target].append(source)
    
    def validate(self) -> Dict[str, Any]:
        """
        Run all validation checks and return structured results.
        
        Returns:
            {
                "valid": bool,
                "errors": [...],
                "warnings": [...],
                "info": [...],
                "summary": {...}
            }
        """
        self.issues = []
        
        # Run validation checks
        self._validate_structure()
        self._validate_nodes()
        self._validate_connections()
        self._validate_flow_logic()
        self._validate_node_configurations()
        
        # Categorize issues
        errors = [i.to_dict() for i in self.issues if i.severity == ValidationSeverity.ERROR]
        warnings = [i.to_dict() for i in self.issues if i.severity == ValidationSeverity.WARNING]
        info = [i.to_dict() for i in self.issues if i.severity == ValidationSeverity.INFO]
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "info": info,
            "summary": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "error_count": len(errors),
                "warning_count": len(warnings),
                "info_count": len(info),
            }
        }
    
    def _validate_structure(self):
        """Validate mandatory workflow structure."""
        
        # Check for Start node (exactly one)
        start_nodes = [n for n in self.nodes if n.get("type") == "start"]
        if not start_nodes:
            self.issues.append(ValidationIssue(
                ValidationSeverity.ERROR,
                "Missing START node - every workflow must begin with a Start node",
                category="structure"
            ))
        elif len(start_nodes) > 1:
            self.issues.append(ValidationIssue(
                ValidationSeverity.ERROR,
                f"Multiple START nodes found ({len(start_nodes)}) - only ONE allowed",
                category="structure"
            ))
        
        # Check for End node (exactly one)
        end_nodes = [n for n in self.nodes if n.get("type") == "end"]
        if not end_nodes:
            self.issues.append(ValidationIssue(
                ValidationSeverity.ERROR,
                "Missing END node - every workflow must end with an End node",
                category="structure"
            ))
        elif len(end_nodes) > 1:
            self.issues.append(ValidationIssue(
                ValidationSeverity.ERROR,
                f"Multiple END nodes found ({len(end_nodes)}) - only ONE allowed",
                category="structure"
            ))
        
        # Check for Delivery node (at least one, unless using Distribute node)
        delivery_types = ["email", "slack", "teams", "saveToSentry"]
        delivery_nodes = [n for n in self.nodes if n.get("type") in delivery_types]
        distribute_nodes = [n for n in self.nodes if n.get("type") == "distribute"]

        # If no distribute node, must have at least 1 delivery node
        # If using distribute node, deliveries must connect through it
        if not delivery_nodes and not distribute_nodes:
            self.issues.append(ValidationIssue(
                ValidationSeverity.ERROR,
                "Missing DELIVERY node - must have at least ONE (Email, Slack, Teams, Save to Sentry, or Distribute)",
                category="structure"
            ))
    
    def _validate_nodes(self):
        """Validate individual nodes exist in registry."""
        
        for node in self.nodes:
            node_type = node.get("type")
            node_id = node.get("id")
            
            if not node_type:
                self.issues.append(ValidationIssue(
                    ValidationSeverity.ERROR,
                    "Node missing type property",
                    node_id=node_id,
                    category="nodes"
                ))
                continue
            
            # Check if node type exists in registry (skip start/end - they're built-in)
            if node_type not in ["start", "end"]:
                try:
                    task_node_type = TaskNodeType(node_type)
                    if task_node_type not in NODE_CATEGORY_INDEX:
                        self.issues.append(ValidationIssue(
                            ValidationSeverity.WARNING,
                            f"Unknown node type '{node_type}' - may not be supported",
                            node_id=node_id,
                            category="nodes"
                        ))
                except ValueError:
                    self.issues.append(ValidationIssue(
                        ValidationSeverity.WARNING,
                        f"Unrecognized node type '{node_type}'",
                        node_id=node_id,
                        category="nodes"
                    ))
    
    def _validate_connections(self):
        """Validate node connections and detect orphaned nodes."""
        
        # Find disconnected nodes (except start/end which might be valid if canvas is empty)
        connected_node_ids = set()
        for edge in self.edges:
            connected_node_ids.add(edge["source"])
            connected_node_ids.add(edge["target"])
        
        for node in self.nodes:
            node_id = node["id"]
            node_type = node.get("type")
            
            # Skip start/end validation if canvas is nearly empty
            if node_type in ["start", "end"] and len(self.nodes) <= 2:
                continue
            
            if node_id not in connected_node_ids:
                node_label = node.get("data", {}).get("label", node_type)
                self.issues.append(ValidationIssue(
                    ValidationSeverity.ERROR,
                    f"Disconnected node '{node_label}' - all nodes must be connected to the workflow",
                    node_id=node_id,
                    category="connections"
                ))
    
    def _validate_flow_logic(self):
        """Validate workflow flow logic and data processing rules."""

        # Rule: Data input nodes MUST connect to an Agent node or Merge node
        data_input_types = ["portfolio", "fileUpload", "oneDrive", "googleDrive"]
        data_input_nodes = [n for n in self.nodes if n.get("type") in data_input_types]

        for data_node in data_input_nodes:
            node_id = data_node["id"]
            node_type = data_node.get("type")

            # Check if this data node connects to an agent or merge node
            downstream_ids = self.edges_by_source.get(node_id, [])
            has_valid_downstream = any(
                self.nodes_by_id.get(target_id, {}).get("type") in ["agent", "merge"]
                for target_id in downstream_ids
            )

            if not has_valid_downstream:
                self.issues.append(ValidationIssue(
                    ValidationSeverity.ERROR,
                    f"Data input '{node_type}' must connect to an AGENT or MERGE node to process the data",
                    node_id=node_id,
                    category="flow"
                ))

        # Rule: Merge nodes MUST have at least 2 inputs and exactly 1 output
        merge_nodes = [n for n in self.nodes if n.get("type") == "merge"]
        for merge_node in merge_nodes:
            node_id = merge_node["id"]

            # Check input count (must have at least 2)
            upstream_ids = self.edges_by_target.get(node_id, [])
            if len(upstream_ids) < 2:
                self.issues.append(ValidationIssue(
                    ValidationSeverity.ERROR,
                    f"Merge node requires at least 2 input connections (currently has {len(upstream_ids)})",
                    node_id=node_id,
                    category="flow"
                ))

            # Check output count (must have exactly 1)
            downstream_ids = self.edges_by_source.get(node_id, [])
            if len(downstream_ids) == 0:
                self.issues.append(ValidationIssue(
                    ValidationSeverity.ERROR,
                    "Merge node must connect to an AGENT node",
                    node_id=node_id,
                    category="flow"
                ))
            elif len(downstream_ids) > 1:
                self.issues.append(ValidationIssue(
                    ValidationSeverity.ERROR,
                    f"Merge node can only connect to ONE output node (currently has {len(downstream_ids)})",
                    node_id=node_id,
                    category="flow"
                ))
            else:
                # Validate that merge node connects to agent
                target_id = downstream_ids[0]
                target_type = self.nodes_by_id.get(target_id, {}).get("type")
                if target_type != "agent":
                    self.issues.append(ValidationIssue(
                        ValidationSeverity.ERROR,
                        f"Merge node must connect to an AGENT node (currently connects to '{target_type}')",
                        node_id=node_id,
                        category="flow"
                    ))

        # Rule: Distribute nodes MUST have exactly 1 input and at least 2 delivery outputs
        distribute_nodes = [n for n in self.nodes if n.get("type") == "distribute"]
        delivery_types = ["email", "slack", "teams", "saveToSentry"]

        for distribute_node in distribute_nodes:
            node_id = distribute_node["id"]

            # Check input count (must have exactly 1)
            upstream_ids = self.edges_by_target.get(node_id, [])
            if len(upstream_ids) == 0:
                self.issues.append(ValidationIssue(
                    ValidationSeverity.ERROR,
                    "Distribute node must have exactly 1 input connection (output or agent)",
                    node_id=node_id,
                    category="flow"
                ))
            elif len(upstream_ids) > 1:
                self.issues.append(ValidationIssue(
                    ValidationSeverity.ERROR,
                    f"Distribute node can only have ONE input (currently has {len(upstream_ids)})",
                    node_id=node_id,
                    category="flow"
                ))

            # Check output count (must have at least 2 delivery nodes)
            downstream_ids = self.edges_by_source.get(node_id, [])
            if len(downstream_ids) == 0:
                self.issues.append(ValidationIssue(
                    ValidationSeverity.ERROR,
                    "Distribute node must connect to at least 2 DELIVERY nodes (Email, Slack, Teams, or Save to Sentry)",
                    node_id=node_id,
                    category="flow"
                ))
            elif len(downstream_ids) < 2:
                self.issues.append(ValidationIssue(
                    ValidationSeverity.WARNING,
                    f"Distribute node should connect to at least 2 delivery channels (currently has {len(downstream_ids)})",
                    node_id=node_id,
                    category="flow"
                ))

            # Validate that all downstream nodes are delivery nodes
            for target_id in downstream_ids:
                target_type = self.nodes_by_id.get(target_id, {}).get("type")
                if target_type not in delivery_types:
                    self.issues.append(ValidationIssue(
                        ValidationSeverity.ERROR,
                        f"Distribute node can only connect to DELIVERY nodes (found '{target_type}')",
                        node_id=node_id,
                        category="flow"
                    ))

        # Rule: Agent nodes should have upstream data or other agents
        agent_nodes = [n for n in self.nodes if n.get("type") == "agent"]
        for agent_node in agent_nodes:
            node_id = agent_node["id"]

            upstream_ids = self.edges_by_target.get(node_id, [])
            if not upstream_ids:
                self.issues.append(ValidationIssue(
                    ValidationSeverity.WARNING,
                    "Agent node has no upstream input - consider connecting data or another agent",
                    node_id=node_id,
                    category="flow"
                ))

        # Suggestion: If canvas has agents but no outputs, suggest adding one
        output_types = ["pdfReport", "pptPresentation", "workbook"]
        has_output = any(n.get("type") in output_types for n in self.nodes)

        if agent_nodes and not has_output and len(self.nodes) > 3:
            self.issues.append(ValidationIssue(
                ValidationSeverity.INFO,
                "Consider adding an OUTPUT node (PDF Report, PowerPoint, or Workbook) for professional formatting",
                category="suggestions"
            ))
    
    def _validate_node_configurations(self):
        """Validate node-specific configuration requirements."""

        for node in self.nodes:
            node_id = node["id"]
            node_type = node.get("type")
            node_data = node.get("data", {})

            # Skip configuration validation for nodes with structural issues
            if node_id in self.invalid_nodes:
                continue

            # Validate Merge nodes
            if node_type == "merge":
                aggregation_mode = node_data.get("aggregationMode", "concatenate")
                if aggregation_mode not in ["concatenate", "structured", "indexed"]:
                    self.issues.append(ValidationIssue(
                        ValidationSeverity.WARNING,
                        f"Unknown aggregation mode '{aggregation_mode}' - defaulting to 'concatenate'",
                        node_id=node_id,
                        category="configuration"
                    ))

            # Validate Agent nodes
            elif node_type == "agent":
                agent_mode = node_data.get("agent")
                if not agent_mode:
                    self.issues.append(ValidationIssue(
                        ValidationSeverity.ERROR,
                        "Agent node missing mode selection - click the node to configure",
                        node_id=node_id,
                        category="configuration"
                    ))
                else:
                    # Check if agent mode exists in registry
                    from core.tasks.types import TaskAgentMode
                    try:
                        mode_enum = TaskAgentMode(agent_mode)
                        if mode_enum not in AGENT_REGISTRY:
                            self.issues.append(ValidationIssue(
                                ValidationSeverity.WARNING,
                                f"Unknown agent mode '{agent_mode}'",
                                node_id=node_id,
                                category="configuration"
                            ))
                    except ValueError:
                        self.issues.append(ValidationIssue(
                            ValidationSeverity.WARNING,
                            f"Invalid agent mode '{agent_mode}'",
                            node_id=node_id,
                            category="configuration"
                        ))
            
            # Validate Email nodes
            elif node_type == "email":
                emails = node_data.get("emails", [])
                email_list_ids = node_data.get("emailListIds", [])
                # Must have at least one email or email list selected
                if (not emails or len(emails) == 0) and (not email_list_ids or len(email_list_ids) == 0):
                    self.issues.append(ValidationIssue(
                        ValidationSeverity.ERROR,
                        "Email node has no recipients - click the node to add email addresses or select email lists",
                        node_id=node_id,
                        category="configuration"
                    ))
            
            # Validate Slack nodes
            elif node_type == "slack":
                channel_ids = node_data.get("channelIds", [])
                if not channel_ids or len(channel_ids) == 0:
                    self.issues.append(ValidationIssue(
                        ValidationSeverity.ERROR,
                        "Slack node missing channel configuration - click the node to configure",
                        node_id=node_id,
                        category="configuration"
                    ))
            
            # Validate Teams nodes
            elif node_type == "teams":
                channel_ids = node_data.get("channelIds", [])
                if not channel_ids or len(channel_ids) == 0:
                    self.issues.append(ValidationIssue(
                        ValidationSeverity.ERROR,
                        "Teams node missing channel configuration - click the node to configure",
                        node_id=node_id,
                        category="configuration"
                    ))
            
            # Validate Portfolio nodes
            elif node_type == "portfolio":
                portfolio_id = node_data.get("portfolioId")
                if not portfolio_id:
                    self.issues.append(ValidationIssue(
                        ValidationSeverity.ERROR,
                        "Portfolio node missing selection - click the node to select a portfolio",
                        node_id=node_id,
                        category="configuration"
                    ))
            
            # Validate File Upload nodes
            elif node_type == "fileUpload":
                file_id = node_data.get("fileId")
                if not file_id:
                    self.issues.append(ValidationIssue(
                        ValidationSeverity.ERROR,
                        "File Upload node missing file - click the node to upload a file",
                        node_id=node_id,
                        category="configuration"
                    ))
            
            # Validate OneDrive nodes
            elif node_type == "oneDrive":
                connected_file = node_data.get("connectedFile")
                if not connected_file:
                    self.issues.append(ValidationIssue(
                        ValidationSeverity.ERROR,
                        "OneDrive node not connected - click the node to connect a file",
                        node_id=node_id,
                        category="configuration"
                    ))
            
            # Validate Google Drive nodes
            elif node_type == "googleDrive":
                connected_file = node_data.get("connectedFile")
                if not connected_file:
                    self.issues.append(ValidationIssue(
                        ValidationSeverity.ERROR,
                        "Google Drive node not connected - click the node to connect a file",
                        node_id=node_id,
                        category="configuration"
                    ))


def validate_canvas(canvas_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main validation entry point.
    
    Args:
        canvas_data: Canvas payload with nodes and edges
    
    Returns:
        Validation results with errors, warnings, and suggestions
    """
    validator = CanvasValidator(canvas_data)
    return validator.validate()
