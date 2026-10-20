"""
Code Execution Tools using OpenAI Code Interpreter

Purpose: Execute Python code using OpenAI's Code Interpreter via Responses API.
Based on official OpenAI documentation for Code Interpreter with containers.
"""

from typing import Optional, Dict, Any, List
import logging
import re

logger = logging.getLogger(__name__)

# Add at module level for the Agents SDK
try:
    from agents import function_tool
except ImportError:
    def function_tool(func):
        return func


async def execute_python_code_raw(
    code: str,
    description: Optional[str] = None,
    session_id: Optional[str] = None,
    selected_model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute Python code using OpenAI Code Interpreter.

    Uses Responses API with automatic container management.
    Containers persist for 20 minutes and are reused automatically.

    Args:
        code: Python code to execute
        description: Optional description
        session_id: Optional session ID
        selected_model: Model to use (Perplexity models not supported)
    """
    try:
        import openai
        from core.config import get_config
        config = get_config()

        client = openai.OpenAI(api_key=config.openai_api_key)

        # Log initial selected_model
        logger.info(f"[DEBUG] Code Interpreter received selected_model: {selected_model}")

        # Dynamic model selection (like other agents)
        if not selected_model:
            from core.config import get_config
            config_model = get_config().agent_model
            # Use gpt-5 for Responses API Code Interpreter
            model = 'gpt-5.4'
        else:
            model = selected_model

        logger.info(f"Using model {model} for Code Interpreter execution")

        # Format the input properly
        input_text = f"{description or 'Execute this Python code:'}\n\n```python\n{code}\n```"

        # Create explicit container per call to avoid stale references
        import uuid
        container_name = f"chat_{uuid.uuid4().hex[:12]}"
        container = client.containers.create(name=container_name)
        container_id = container.id

        # Call Responses API with Code Interpreter using explicit container
        response = client.responses.create(
            model=model,  # Use selected model or fallback
            tools=[{
                "type": "code_interpreter",
                "container": container_id  # Explicit container
            }],
            instructions="You are QuantCoder, a quantitative finance code executor. Execute the provided Python code and return results.",
            input=input_text
        )

        # Parse the response - just get the attributes directly

        # Log what we actually get from the response
        logger.info(f"[DEBUG] Response type: {type(response)}")
        logger.info(f"[DEBUG] Response attributes: {dir(response)}")
        if hasattr(response, 'output'):
            logger.info(f"[DEBUG] Output object: {response.output}")
            logger.info(f"[DEBUG] Output type: {type(response.output)}")
            if response.output:
                logger.info(f"[DEBUG] Output attributes: {dir(response.output)}")
        if hasattr(response, 'output_text'):
            logger.info(f"[DEBUG] Output text (first 500 chars): {str(response.output_text)[:500]}")

        # Extract file citations from assistant message content annotations (per OpenAI docs)
        container_id = None
        generated_files = []

        if hasattr(response, 'output') and response.output:
            for message in response.output:
                # Look for assistant messages (per docs structure)
                if hasattr(message, 'role') and message.role == 'assistant':
                    if hasattr(message, 'content') and message.content:
                        for content_item in message.content:
                            if hasattr(content_item, 'annotations') and content_item.annotations:
                                for annotation in content_item.annotations:
                                    if annotation.type == 'container_file_citation':
                                        container_id = annotation.container_id
                                        file_info = {
                                            'container_id': annotation.container_id,
                                            'file_id': annotation.file_id,
                                            'filename': annotation.filename,
                                            'type': 'file'
                                        }
                                        generated_files.append(file_info)
                                        logger.info(f"Found file: {annotation.filename} ({annotation.file_id})")

        # If no files found in annotations but we have container_id, list files proactively
        if not generated_files and container_id:
            try:
                files_response = client.containers.files.list(container_id)
                for file_obj in files_response.data:
                    filename = file_obj.path.split('/')[-1] if file_obj.path else f"file_{file_obj.id}"
                    file_info = {
                        'container_id': container_id,
                        'file_id': file_obj.id,
                        'filename': filename,
                        'type': 'file'
                    }
                    generated_files.append(file_info)
                    logger.info(f"Discovered file: {filename} ({file_obj.id})")
            except Exception as e:
                logger.warning(f"Could not list container files: {e}")

        # Put metadata directly in the response string - this is what the extraction logic reads
        output_text = str(response.output_text) if hasattr(response, 'output_text') else ""

        # Just return the output_text with container ID injected for the regex to find
        if container_id:
            output_text += f"\n\nContainer: {container_id}"

        # Return a properly structured dictionary with all metadata
        return {
            "status": "success",
            "output_text": output_text,
            "container_id": container_id,
            "generated_files": generated_files
        }

    except Exception as e:
        logger.error(f"Code execution failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "output_text": f"Execution failed: {str(e)}"
        }
    finally:
        # Cleanup container to avoid lingering resources
        try:
            if container_id:
                client.containers.delete(container_id)
                logger.info(f"[CONTAINER] Deleted {container_id}")
        except Exception:
            pass


async def download_file_from_code_interpreter(
    file_id: str,
    container_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Download a file from OpenAI Code Interpreter container.

    Args:
        file_id: The file ID from Code Interpreter
        container_id: Optional container ID (if available)

    Returns:
        Dict with file content and metadata
    """
    try:
        import httpx
        from core.config import get_config
        config = get_config()

        # Direct HTTP download from OpenAI container (same pattern as workbook_generator.py)
        url = f"https://api.openai.com/v1/containers/{container_id}/files/{file_id}/content"

        with httpx.Client(timeout=60.0) as client:
            response = client.get(
                url,
                headers={
                    "Authorization": f"Bearer {config.openai_api_key}",
                    "OpenAI-Beta": "containers=v1"
                }
            )
            response.raise_for_status()
            content_bytes = response.content

        return {
            "status": "success",
            "file_id": file_id,
            "filename": filename or f"file_{file_id}",
            "content_bytes": content_bytes,
            "size_bytes": len(content_bytes),
            "mime_type": "application/octet-stream"  # Could be enhanced with file type detection
        }

    except Exception as e:
        logger.error(f"File download failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "file_id": file_id
        }


async def list_generated_files(session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    List all files generated in the current Code Interpreter session.

    Args:
        session_id: Optional session identifier

    Returns:
        Dict with list of generated files
    """
    try:
        # This would typically retrieve from a session store
        # For now, return a placeholder structure
        return {
            "status": "success",
            "files": [],
            "message": "File listing requires active session tracking"
        }
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


# Wrap for Agents SDK
execute_python_code = function_tool(execute_python_code_raw)
download_file = function_tool(download_file_from_code_interpreter)
list_files = function_tool(list_generated_files)
