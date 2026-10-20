"""
Simple workflow executor - chains agent prompts
"""
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class SimpleWorkflow:
    """Execute a chain of agent prompts sequentially."""
    
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
    
    async def run(self, nodes: List[Dict], initial_input: str, user_id: str) -> Dict[str, Any]:
        """
        Run nodes in sequence, passing context forward.
        
        Args:
            nodes: List of node definitions with agent and prompt
            initial_input: Starting input (e.g., ticker symbol)
            user_id: User ID for RLS context
            
        Returns:
            Dict with final result and intermediate outputs
        """
        context = {"input": initial_input}
        outputs = []
        
        for node in nodes:
            # Format prompt with all previous context
            prompt = node["prompt"].format(**context)
            
            # Execute via orchestrator
            result = await self.orchestrator.process_message(
                prompt, 
                user_id=user_id
            )
            
            # Store for next node and output
            context[f"node_{node['id']}"] = result
            outputs.append({"node_id": node['id'], "output": result})
            
        return {"final": outputs[-1]["output"] if outputs else "", "steps": outputs}