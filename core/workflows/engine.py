"""
Workflow Engine - Simplified
Status: Production
Created: September 2025
Updated: October 2025 - Simplified for linear workflows

PURPOSE: Execute simplified workflows (Input → Agents → Output).
NO HARDCODING - all behavior driven by SimplifiedWorkflow structure.
KISS principle: Simple sequential execution with background processing.
"""

from typing import Dict, Any, Optional
import asyncio
import json
import uuid
import logging
from datetime import datetime
from uuid import UUID
import os
import aiofiles

from core.database.postgres_client import get_postgres_rls_client
from core.workflows.validation import WorkflowValidator
from core.workflows.types import (
    SimplifiedWorkflow, InputNode, AgentNode, OutputNode,
    InputNodeType, OutputNodeType, AgentNodeType
)
from api.orchestrator import get_v6_orchestrator
from core.config import get_config
from core.integrations.gamma_client import get_gamma_client, build_instructions_from_settings
from api.routers.user_settings import fetch_user_export_style
from core.services.artifact_storage import get_artifact_storage

logger = logging.getLogger(__name__)

# Keep strong references to background tasks to prevent garbage collection
_background_tasks: set = set()


def truncate_output(output: Any, max_size: int = 102400) -> Any:
    """Truncate output if too large (100KB default) to prevent DB bloat"""
    if isinstance(output, dict):
        output_str = json.dumps(output)
        if len(output_str) > max_size:
            logger.warning(f"Truncating output from {len(output_str)} to {max_size} bytes")
            return {"truncated": True, "preview": output_str[:max_size]}
    elif isinstance(output, str) and len(output) > max_size:
        logger.warning(f"Truncating string output from {len(output)} to {max_size} bytes")
        return output[:max_size] + "... [truncated]"
    return output


class WorkflowEngine:
    """Simplified workflow executor for linear agent chains"""

    async def run_workflow_async(self, workflow_id: str, user_id: str) -> str:
        """
        Start workflow execution asynchronously.
        Creates run record and starts background execution.
        Returns run_id immediately for polling.
        """
        run_id = str(uuid.uuid4())
        pg = await get_postgres_rls_client()

        logger.info(f"[WORKFLOW RUN] Creating run: run_id={run_id}, workflow_id={workflow_id}, user_id={user_id}")

        # First, get the workflow's org_id for proper RLS context
        async with pg.pool.acquire() as conn:
            workflow_row = await conn.fetchrow(
                "SELECT org_id FROM workflows WHERE id = $1 AND deleted_at IS NULL",
                workflow_id
            )
            if not workflow_row:
                raise ValueError(f"Workflow {workflow_id} not found")
            org_id = workflow_row['org_id']

        # Create run record with 'queued' status (use org context)
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            # Create run record
            logger.info(f"[WORKFLOW RUN] Attempting INSERT into workflow_runs: run_id={run_id}, org_id={org_id}")
            await conn.execute(
                """
                INSERT INTO workflow_runs (
                    id, workflow_id, user_id, org_id, status,
                    input_data, output_data, configuration,
                    created_at, updated_at
                ) VALUES ($1, $2, $3, $4, 'queued', '{}', '{}', '{}', NOW(), NOW())
                """,
                run_id, workflow_id, user_id, org_id
            )
            logger.info(f"[WORKFLOW RUN] INSERT succeeded: run_id={run_id}")

            # Verify row exists immediately
            check_count = await conn.fetchval("SELECT COUNT(*) FROM workflow_runs WHERE id = $1", run_id)
            logger.info(f"[WORKFLOW RUN] Verification query returned count: {check_count} for run_id={run_id}")

            # Also check with user_id filter
            check_with_user = await conn.fetchval(
                "SELECT COUNT(*) FROM workflow_runs WHERE id = $1 AND user_id = $2",
                run_id, user_id
            )
            logger.info(f"[WORKFLOW RUN] Verification with user_id filter returned count: {check_with_user}")

        # Execute workflow in background
        logger.info(f"[WORKFLOW RUN] Starting background execution for run_id={run_id}")
        task = asyncio.create_task(self._execute_workflow_async(workflow_id, user_id, run_id))
        # Keep strong reference to prevent garbage collection during long-running PDF/PPT generation
        _background_tasks.add(task)
        task.add_done_callback(lambda t: _background_tasks.discard(t))
        return run_id

    async def _execute_workflow_async(self, workflow_id: str, user_id: str, run_id: str) -> None:
        """
        Background execution of simplified workflow.
        Updates run record as execution progresses.
        """
        logger.info(f"[WORKFLOW EXEC] Background task started: run_id={run_id}, workflow_id={workflow_id}, user_id={user_id}")

        # Load org_id from run record for proper RLS context
        pg = await get_postgres_rls_client()
        async with pg.pool.acquire() as conn:
            run_row = await conn.fetchrow("SELECT org_id FROM workflow_runs WHERE id = $1", run_id)
            if not run_row:
                logger.error(f"[WORKFLOW EXEC] Run not found: {run_id}")
                return
            org_id = run_row['org_id']

        try:
            # 1. Load workflow
            logger.info(f"[WORKFLOW EXEC] Loading workflow: workflow_id={workflow_id}, org_id={org_id}")
            workflow = await self._load_simplified_workflow(workflow_id, user_id, org_id)
            logger.info(f"[WORKFLOW EXEC] Workflow loaded successfully with {len(workflow.agent_nodes)} agents")

            # 2. Validate
            validator = WorkflowValidator()
            validation_result = validator.validate_simplified(workflow)
            if not validation_result.is_valid:
                error_msg = "; ".join(validation_result.errors)
                await self._update_run_status(run_id, user_id, org_id, 'failed', error=error_msg)
                return

            # 3. Create step records for each agent
            async with pg.acquire_with_org_context(user_id, org_id) as conn:
                for idx, agent in enumerate(workflow.agent_nodes):
                    await conn.execute(
                        """
                        INSERT INTO workflow_run_steps (
                            run_id, node_id, node_type, node_label,
                            status, execution_order, input_data, output_data
                        ) VALUES ($1, $2, 'agent', $3, 'pending', $4, '{}', '{}')
                        """,
                        run_id, agent.id,
                        f"Agent {idx + 1}: {agent.agent_type.value}", idx
                    )

                # Also create step record for output node
                output_order = len(workflow.agent_nodes)
                await conn.execute(
                    """
                    INSERT INTO workflow_run_steps (
                        run_id, node_id, node_type, node_label,
                        status, execution_order, input_data, output_data
                    ) VALUES ($1, $2, 'output', $3, 'pending', $4, '{}', '{}')
                    """,
                    run_id, workflow.output_node.id,
                    workflow.output_node.title or 'Workflow Output', output_order
                )

            # 4. Update run status to running
            await self._update_run_status(run_id, user_id, org_id, 'running')

            # 5. Load input
            context = await self._load_input(workflow.input_node, user_id)

            # 6. Chain through agents sequentially (DIRECT EXECUTION - no supervisor)
            orchestrator = get_v6_orchestrator()

            # Map agent types to orchestrator agent instances
            agent_map = {
                "generalist": getattr(orchestrator, "main_agent", None),
                "risk_specialist": getattr(orchestrator, "risk_specialist", None),
                "document_analyst": getattr(orchestrator, "document_analyst", None),
                "comparable_companies": getattr(orchestrator, "comparable_companies", None),
                "chart_analyst": getattr(orchestrator, "chart_analyst", None),
                "quant_coding": getattr(orchestrator, "quant_coding", None),
                "dcf_agent": getattr(orchestrator, "dcf_agent", None),
                "alternatives_coding": getattr(orchestrator, "alternatives_coding", None),
                "institutional_activity": getattr(orchestrator, "institutional_activity", None),
                "options_coding": getattr(orchestrator, "options_coding", None),
                "funds_products_analyst": getattr(orchestrator, "funds_products_analyst", None),
                "prediction_markets_analyst": getattr(orchestrator, "prediction_markets_analyst", None),
            }

            # Use SQLite session for agent execution (same as orchestrator)
            from agents import Runner, SQLiteSession
            from core.ai.langgraph_utils import trim_sqlite_session_history
            workflow_session_id = f"workflow_{run_id}"
            session = SQLiteSession(workflow_session_id, orchestrator.db_path)

            # Set user context for tools to access
            from core.utils.context_utils import user_context, session_context
            tok_u = user_context.set(user_id) if user_id else None
            tok_s = session_context.set(workflow_session_id)

            try:
                for idx, agent in enumerate(workflow.agent_nodes):
                    # Update step to running
                    await self._update_step_status(run_id, agent.id, user_id, org_id, 'running')

                    # Always build complete prompt with context
                    prompt = agent.custom_prompt
                    if context.get("input"):
                        prompt += f"\n\nInput data:\n{context['input']}"
                    if context.get("previous_output"):
                        prompt += f"\n\nPrevious analysis:\n{context['previous_output']}"

                    # Get agent instance
                    agent_instance = agent_map.get(agent.agent_type.value)
                    if not agent_instance:
                        error_msg = f"Agent {idx + 1}: Agent type '{agent.agent_type.value}' not available"
                        logger.error(error_msg)
                        await self._update_step_status(run_id, agent.id, user_id, org_id, 'failed')
                        await self._update_run_status(run_id, user_id, org_id, 'failed', error=error_msg)
                        return

                    # Execute agent DIRECTLY (bypass supervisor)
                    try:
                        logger.info(f"[WORKFLOW] Executing agent {idx + 1}/{len(workflow.agent_nodes)}: {agent.agent_type.value}")
                        selected_model = getattr(agent_instance, "model", None)
                        selected_model_str = (
                            selected_model
                            if isinstance(selected_model, str)
                            else (str(selected_model) if selected_model is not None else None)
                        )
                        await trim_sqlite_session_history(
                            session,
                            selected_model_str,
                            f"workflow_{agent.agent_type.value}",
                        )
                        result = await Runner.run(agent_instance, prompt, session=session)

                        # Extract response
                        response = result.final_output if hasattr(result, 'final_output') else str(result)

                        # Extract code execution data from Runner.run result
                        code_execution_data = None

                        # For quant_coding and dcf_agent, extract code blocks from response
                        if agent.agent_type.value in ["quant_coding", "dcf_agent"]:
                            code_blocks = []
                            generated_files = []
                            container_id = None

                            # Extract code blocks from markdown in response text
                            if isinstance(response, str) and "```" in response:
                                try:
                                    import re
                                    # Look for code blocks in markdown format
                                    code_matches = re.findall(r"```(?:python|Python)?\s*\n(.*?)\n?```", response, re.DOTALL | re.MULTILINE)
                                    for code_match in code_matches:
                                        if isinstance(code_match, str) and code_match.strip():
                                            code_blocks.append({
                                                "code": code_match,
                                                "output": "",
                                                "language": "python"
                                            })
                                    if code_blocks:
                                        logger.info(f"[WORKFLOW] Extracted {len(code_blocks)} code blocks from response")
                                except Exception as e:
                                    logger.warning(f"[WORKFLOW] Failed to extract code blocks: {e}")

                            # Look for sandbox file references in response
                            if isinstance(response, str) and "sandbox:/mnt/data/" in response:
                                try:
                                    import re
                                    file_matches = set(re.findall(r"sandbox:/mnt/data/([A-Za-z0-9_\-.() ]+\.[A-Za-z0-9]+)", response))
                                    for filename in file_matches:
                                        if filename and not filename.endswith('/'):
                                            generated_files.append({
                                                "filename": filename.strip(),
                                                "type": "file",
                                                "file_id": None
                                            })
                                    if generated_files:
                                        logger.info(f"[WORKFLOW] Found {len(generated_files)} generated files in response")
                                except Exception:
                                    pass

                            # Check result object for container_id (from code interpreter)
                            if hasattr(result, 'new_items') and result.new_items:
                                for item in result.new_items:
                                    if hasattr(item, 'type') and item.type == 'code_interpreter_call':
                                        if hasattr(item, 'container_id') and item.container_id:
                                            container_id = item.container_id
                                            logger.info(f"[WORKFLOW] Found container_id: {container_id}")
                                            break

                            if code_blocks or generated_files or container_id:
                                code_execution_data = {
                                    "code_blocks": code_blocks,
                                    "generated_files": generated_files,
                                    "container_id": container_id
                                }
                                logger.info(f"[WORKFLOW] Created code_execution_data: {len(code_blocks)} blocks, {len(generated_files)} files")

                        # Update context for next agent - accumulate all outputs
                        prev = context.get("previous_output", "")
                        context["previous_output"] = f"{prev}\n\n--- Agent {idx + 1} ({agent.agent_type.value}) ---\n\n{response}" if prev else response
                        # Store as dict for PDF/PPT generation compatibility
                        context[f"agent_{idx + 1}"] = {
                            "content": response,
                            "charts": [],
                            "sources": [],
                            "code_execution_data": code_execution_data
                        }

                        # Store at context root for final output node
                        if code_execution_data:
                            context["code_execution_data"] = code_execution_data

                        # Update step as succeeded
                        await self._update_step_status(
                            run_id, agent.id, user_id, org_id, 'succeeded',
                            output=truncate_output({"result": response})
                        )

                        logger.info(f"[WORKFLOW] Agent {idx + 1} completed successfully")

                    except Exception as agent_error:
                        error_msg = f"Agent {idx + 1} ({agent.agent_type.value}): {str(agent_error)}"
                        logger.error(error_msg, exc_info=True)
                        await self._update_step_status(run_id, agent.id, user_id, org_id, 'failed')
                        await self._update_run_status(run_id, user_id, org_id, 'failed', error=error_msg)
                        return
            finally:
                # Always reset context
                if tok_u:
                    user_context.reset(tok_u)
                if tok_s:
                    session_context.reset(tok_s)

            # 7. Format output
            # Update output node step to running
            await self._update_step_status(run_id, workflow.output_node.id, user_id, org_id, 'running')

            final_output = await self._format_output(context, workflow.output_node, run_id, user_id)

            # Update output node step to succeeded
            await self._update_step_status(
                run_id, workflow.output_node.id, user_id, org_id, 'succeeded',
                output=truncate_output(final_output)
            )

            # 8. Save successful result
            await self._update_run_status(
                run_id, user_id, org_id, 'succeeded',
                result=truncate_output(final_output)
            )

        except Exception as e:
            error_msg = f"Workflow execution failed: {str(e)}"
            logger.error(f"[WORKFLOW EXEC] ERROR in background task: {error_msg}", exc_info=True)
            try:
                await self._update_run_status(run_id, user_id, org_id, 'failed', error=error_msg)
                logger.info(f"[WORKFLOW EXEC] Updated run status to 'failed' for run_id={run_id}")
            except Exception as update_error:
                logger.error(f"[WORKFLOW EXEC] Failed to update run status: {update_error}", exc_info=True)

    async def _load_simplified_workflow(self, workflow_id: str, user_id: str, org_id: str = None) -> SimplifiedWorkflow:
        """Load SimplifiedWorkflow from database"""
        pg = await get_postgres_rls_client()

        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            row = await conn.fetchrow(
                """
                SELECT configuration, nodes, edges
                FROM workflows
                WHERE id = $1 AND deleted_at IS NULL
                """,
                workflow_id
            )

            if not row:
                raise ValueError(f"Workflow {workflow_id} not found")

            # Parse configuration
            config = json.loads(row["configuration"]) if row["configuration"] else {}

            # Check if it's simplified format
            if config.get("format") == "simplified" or "input_node" in config:
                return SimplifiedWorkflow(
                    input_node=InputNode(**config["input_node"]),
                    agent_nodes=[AgentNode(**a) for a in config["agent_nodes"]],
                    output_node=OutputNode(**config["output_node"])
                )
            else:
                raise ValueError("Workflow is in legacy format - cannot execute with simplified engine")

    async def _load_input(self, input_node: InputNode, user_id: str) -> Dict[str, Any]:
        """Load input data based on input node type"""
        if input_node.type == InputNodeType.PORTFOLIO:
            # Load portfolio from database using same method as chat
            if not input_node.portfolio_id:
                raise ValueError("Portfolio ID is not configured for this workflow")

            pg = await get_postgres_rls_client()
            portfolio_data = await pg.get_portfolio_by_id(user_id=user_id, portfolio_id=input_node.portfolio_id)

            if not portfolio_data:
                raise ValueError(f"Portfolio {input_node.portfolio_id} not found")

            # Parse holdings if it's a JSON string (from PostgreSQL JSONB)
            holdings_data = portfolio_data.get("holdings", [])
            if isinstance(holdings_data, str):
                try:
                    holdings_data = json.loads(holdings_data)
                except Exception:
                    holdings_data = []
                portfolio_data["holdings"] = holdings_data

            # Format portfolio info for prompt (include holdings summary if available)
            tickers = portfolio_data.get("tickers", [])
            weights = portfolio_data.get("weights", [])
            portfolio_str = f"Portfolio '{portfolio_data['name']}' with {len(tickers)} positions:\n"
            for ticker, weight in zip(tickers, weights):
                portfolio_str += f"- {ticker}: {weight * 100:.1f}%\n"

            # Add holdings summary if available
            if holdings_data:
                portfolio_str += f"\nDetailed holdings with {sum(len(h.get('lots', [])) for h in holdings_data)} purchase lots available for P&L analysis."

            return {"input": portfolio_str, "portfolio_data": portfolio_data}

        elif input_node.type == InputNodeType.UPLOADED_FILE:
            # Pass file_id to agent (same pattern as chat) - don't pre-read content
            # Agent will use its file reading tools to analyze the file
            if not input_node.file_id:
                raise ValueError("File ID is not configured for this workflow")

            # Just pass the file_id - agent will read it using file_tools
            return {
                "input": f"Analyze the uploaded file (file_id: {input_node.file_id})",
                "file_id": input_node.file_id,
                "file_ids": [input_node.file_id]  # Match chat format
            }

        elif input_node.type == InputNodeType.EXTERNAL_DATA:
            # External data (Google Drive, OneDrive) - same as uploaded_file
            # File is already uploaded via uploadService, just pass file_id
            if not input_node.file_id:
                raise ValueError("File ID is not configured for this workflow")

            source = input_node.external_source or "external source"
            return {
                "input": f"Analyze the file from {source} (file_id: {input_node.file_id})",
                "file_id": input_node.file_id,
                "file_ids": [input_node.file_id]
            }

        elif input_node.type == InputNodeType.PROMPT:
            # Just use the prompt text
            if not input_node.prompt_text:
                raise ValueError("Prompt text is not configured for this workflow")
            return {"input": input_node.prompt_text}

        else:
            raise ValueError(f"Unknown input type: {input_node.type}")

    async def _format_output(self, context: Dict[str, Any], output_node: OutputNode, run_id: str, user_id: str) -> Dict[str, Any]:
        """Format final output based on output node type"""
        # Get final result - will be a string from direct agent execution
        final_result = context.get("previous_output", "")

        # Ensure it's a string for content generation
        if isinstance(final_result, dict):
            final_result = final_result.get("content", str(final_result))
        elif not isinstance(final_result, str):
            final_result = str(final_result)

        if output_node.type == OutputNodeType.TEXT:
            # Append code execution details if present
            code_data = context.get("code_execution_data")
            if code_data:
                code_blocks = code_data.get('code_blocks', [])
                generated_files = code_data.get('generated_files', [])

                if code_blocks or generated_files:
                    final_result += "\n\n--- CODE EXECUTION SUMMARY ---\n"

                    if code_blocks:
                        final_result += f"\n**Executed {len(code_blocks)} code block(s)**:\n"
                        for idx, block in enumerate(code_blocks, 1):
                            final_result += f"\n```python\n{block['code']}\n```\n"

                    if generated_files:
                        final_result += f"\n**Generated {len(generated_files)} file(s)**:\n"
                        for f in generated_files:
                            final_result += f"- {f['filename']} ({f['type']})\n"

            # Return as plain text with code_execution_data attached
            return {
                "type": "text",
                "content": final_result,
                "title": output_node.title,
                "code_execution_data": code_data
            }

        elif output_node.type == OutputNodeType.PDF:
            # Fetch user export settings
            user_settings = await fetch_user_export_style(user_id)
            gamma_client = get_gamma_client()

            # Build natural language instructions from user settings
            final_instructions = build_instructions_from_settings(
                base_prompt=user_settings.custom_prompt,
                verbosity=user_settings.verbosity,
                tone=user_settings.tone,
                audience=user_settings.audience
            )

            # Build card options with logo from user settings
            card_options = None
            if user_settings.logo_source != "none":
                header_footer = {
                    "bottomRight": {"type": "cardNumber"},
                    "hideFromFirstCard": True
                }

                logo_config = {
                    "type": "image",
                    "source": user_settings.logo_source,
                    "size": user_settings.logo_size
                }

                if user_settings.logo_source == "custom" and user_settings.logo_url:
                    logo_config["src"] = user_settings.logo_url

                header_footer[user_settings.logo_position] = logo_config
                card_options = {"headerFooter": header_footer}

            # Generate PDF with Gamma API
            pdf_bytes = await gamma_client.generate_presentation(
                content=final_result,
                format="document",
                export_as="pdf",
                theme_id=user_settings.theme_id,
                text_options={"language": user_settings.language},
                additional_instructions=final_instructions,
                cardOptions=card_options
            )

            if pdf_bytes is None:
                raise RuntimeError("Failed to generate PDF export for workflow")

            # Save to filesystem
            workflow_dir = "/tmp/workflows"
            os.makedirs(workflow_dir, exist_ok=True)

            pdf_filename = f"workflow_{run_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            pdf_path = os.path.join(workflow_dir, pdf_filename)

            with open(pdf_path, 'wb') as f:
                f.write(pdf_bytes)

            logger.info(f"[PDF] Generated PDF: {pdf_path}")

            artifact_storage = get_artifact_storage()
            await artifact_storage.persist_local_file("workflows", pdf_filename, pdf_path)

            result_dict = {
                "type": "pdf",
                "content": final_result,
                "title": output_node.title or "Workflow Report",
                "pdf_path": pdf_path,
                "pdf_filename": pdf_filename,
                "download_url": f"/api/workflows/download/{pdf_filename}"
            }
            logger.info(f"[PDF] Returning result dict with keys: {list(result_dict.keys())}")
            return result_dict

        elif output_node.type == OutputNodeType.PRESENTATION:
            # Fetch user export settings
            user_settings = await fetch_user_export_style(user_id)
            gamma_client = get_gamma_client()

            # Build natural language instructions from user settings
            final_instructions = build_instructions_from_settings(
                base_prompt=user_settings.custom_prompt,
                verbosity=user_settings.verbosity,
                tone=user_settings.tone,
                audience=user_settings.audience
            )

            # Build card options with logo from user settings
            card_options = None
            if user_settings.logo_source != "none":
                header_footer = {
                    "bottomRight": {"type": "cardNumber"},
                    "hideFromFirstCard": True
                }

                logo_config = {
                    "type": "image",
                    "source": user_settings.logo_source,
                    "size": user_settings.logo_size
                }

                if user_settings.logo_source == "custom" and user_settings.logo_url:
                    logo_config["src"] = user_settings.logo_url

                header_footer[user_settings.logo_position] = logo_config
                card_options = {"headerFooter": header_footer}

            # Generate PPTX with Gamma API
            ppt_bytes = await gamma_client.generate_presentation(
                content=final_result,
                format="presentation",
                export_as="pptx",
                theme_id=user_settings.theme_id,
                text_options={"language": user_settings.language},
                additional_instructions=final_instructions,
                cardOptions=card_options
            )

            if ppt_bytes is None:
                raise RuntimeError("Failed to generate presentation export for workflow")

            # Save to filesystem
            workflow_dir = "/tmp/workflows"
            os.makedirs(workflow_dir, exist_ok=True)

            ppt_filename = f"workflow_{run_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
            ppt_path = os.path.join(workflow_dir, ppt_filename)

            with open(ppt_path, 'wb') as f:
                f.write(ppt_bytes)

            logger.info(f"Generated PDF: {ppt_path}")

            artifact_storage = get_artifact_storage()
            await artifact_storage.persist_local_file("workflows", ppt_filename, ppt_path)

            return {
                "type": "presentation",
                "content": final_result,
                "title": output_node.title or "Workflow Presentation",
                "ppt_path": ppt_path,
                "ppt_filename": ppt_filename,
                "download_url": f"/api/workflows/download/{ppt_filename}"
            }

        else:
            raise ValueError(f"Unknown output type: {output_node.type}")

    async def _update_run_status(
        self,
        run_id: str,
        user_id: str,
        org_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> None:
        """Update workflow run status in database"""
        pg = await get_postgres_rls_client()

        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            if status == 'running':
                await conn.execute(
                    """
                    UPDATE workflow_runs
                    SET status = $1, started_at = NOW(), updated_at = NOW()
                    WHERE id = $2
                    """,
                    status, run_id
                )
            elif status in ('succeeded', 'failed'):
                await conn.execute(
                    """
                    UPDATE workflow_runs
                    SET status = $1, summary = $2, error = $3,
                        completed_at = NOW(), updated_at = NOW()
                    WHERE id = $4
                    """,
                    status,
                    json.dumps(result) if result else None,
                    error,
                    run_id
                )
            else:
                await conn.execute(
                    "UPDATE workflow_runs SET status = $1, updated_at = NOW() WHERE id = $2",
                    status, run_id
                )

    async def _update_step_status(
        self,
        run_id: str,
        node_id: str,
        user_id: str,
        org_id: str,
        status: str,
        output: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update individual step status in database"""
        logger.info(f"[WORKFLOW STEP] Updating step: run_id={run_id}, node_id={node_id}, status={status}")

        pg = await get_postgres_rls_client()

        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            if status == 'running':
                logger.info(f"[WORKFLOW STEP] Setting node {node_id} to 'running' with started_at=NOW()")
                await conn.execute(
                    """
                    UPDATE workflow_run_steps
                    SET status = $1, started_at = NOW()
                    WHERE run_id = $2 AND node_id = $3
                    """,
                    status, run_id, node_id
                )
            elif status in ('succeeded', 'failed'):
                logger.info(f"[WORKFLOW STEP] Setting node {node_id} to '{status}' with completed_at=NOW()")
                await conn.execute(
                    """
                    UPDATE workflow_run_steps
                    SET status = $1, output_data = $2, completed_at = NOW()
                    WHERE run_id = $3 AND node_id = $4
                    """,
                    status,
                    json.dumps(output) if output else '{}',
                    run_id, node_id
                )

        logger.info(f"[WORKFLOW STEP] Successfully updated node {node_id} to status '{status}'")
