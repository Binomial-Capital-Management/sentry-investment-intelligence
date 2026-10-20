"""
Canvas Process Primitives - Tensor-based process graph system

Uses a 2D coordinate system: [primitive_type, instance]
- 1 = data (raw data sources)
- 2 = truth (derived facts/state)
- 3 = action (transformations)
- 4 = output (results/artifacts)
- 5 = system (external connections)

Any tool can use these primitives to build its process graph.
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import IntEnum


class PrimitiveType(IntEnum):
    """Primitive type indices for the tensor coordinate system."""
    DATA = 1
    TRUTH = 2
    ACTION = 3
    OUTPUT = 4
    SYSTEM = 5


@dataclass
class ProcessStep:
    """A single step in a process graph."""
    coord: Tuple[int, int]  # [primitive_type, instance]
    primitive: str  # 'data', 'truth', 'action', 'output', 'system'
    label: str
    value: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "coord": list(self.coord),
            "primitive": self.primitive,
            "label": self.label,
            "value": self.value,
        }


@dataclass
class ProcessEdge:
    """An edge connecting two steps in a process graph."""
    source: Tuple[int, int]
    target: Tuple[int, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": list(self.source),
            "target": list(self.target),
        }


class ProcessGraphBuilder:
    """
    Builder for constructing process graphs using the primitive system.
    
    Example usage:
        builder = ProcessGraphBuilder()
        builder.add_data(1, "Portfolio", ["AAPL", "MSFT"])
        builder.add_system(1, "Market Data API")
        builder.add_truth(1, "Historical Returns")
        builder.add_action(1, "Monte Carlo Simulation", {"simulations": 1000})
        builder.add_output(1, "Price Paths")
        builder.add_output(2, "Distribution")
        builder.add_output(3, "Statistics")
        builder.connect((1, 1), (5, 1))  # data -> system
        builder.connect((5, 1), (2, 1))  # system -> truth
        builder.connect((2, 1), (3, 1))  # truth -> action
        builder.connect((3, 1), (4, 1))  # action -> output1
        builder.connect((3, 1), (4, 2))  # action -> output2
        builder.connect((3, 1), (4, 3))  # action -> output3
        steps, edges = builder.build()
    """

    def __init__(self):
        self._steps: List[ProcessStep] = []
        self._edges: List[ProcessEdge] = []

    def add_data(self, instance: int, label: str, value: Any = None) -> "ProcessGraphBuilder":
        """Add a data primitive node."""
        self._steps.append(ProcessStep(
            coord=(PrimitiveType.DATA, instance),
            primitive="data",
            label=label,
            value=value,
        ))
        return self

    def add_truth(self, instance: int, label: str, value: Any = None) -> "ProcessGraphBuilder":
        """Add a truth primitive node."""
        self._steps.append(ProcessStep(
            coord=(PrimitiveType.TRUTH, instance),
            primitive="truth",
            label=label,
            value=value,
        ))
        return self

    def add_action(self, instance: int, label: str, value: Any = None) -> "ProcessGraphBuilder":
        """Add an action primitive node."""
        self._steps.append(ProcessStep(
            coord=(PrimitiveType.ACTION, instance),
            primitive="action",
            label=label,
            value=value,
        ))
        return self

    def add_output(self, instance: int, label: str, value: Any = None) -> "ProcessGraphBuilder":
        """Add an output primitive node."""
        self._steps.append(ProcessStep(
            coord=(PrimitiveType.OUTPUT, instance),
            primitive="output",
            label=label,
            value=value,
        ))
        return self

    def add_system(self, instance: int, label: str, value: Any = None) -> "ProcessGraphBuilder":
        """Add a system primitive node."""
        self._steps.append(ProcessStep(
            coord=(PrimitiveType.SYSTEM, instance),
            primitive="system",
            label=label,
            value=value,
        ))
        return self

    def connect(self, source: Tuple[int, int], target: Tuple[int, int]) -> "ProcessGraphBuilder":
        """Connect two nodes by their coordinates."""
        self._edges.append(ProcessEdge(source=source, target=target))
        return self

    def build(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Build and return the graph as (steps, edges) dictionaries."""
        steps = [s.to_dict() for s in self._steps]
        edges = [e.to_dict() for e in self._edges]
        return steps, edges
