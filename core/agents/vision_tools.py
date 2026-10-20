"""Vision tools for GPT-5 image and PDF analysis."""

import os
import base64
import io
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

def analyze_image_with_gpt5(image_path: str, prompt: str = None) -> Dict[str, Any]:
    """
    Analyze image using GPT-5 vision capabilities.

    Args:
        image_path: Path to image file
        prompt: Optional custom prompt

    Returns:
        Analysis results with extracted information
    """
    try:
        from openai import OpenAI
        from PIL import Image
    except ImportError:
        return {"error": "Required packages not installed"}

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return {"error": "OPENAI_API_KEY not configured"}

    # Get model from env or use default
    model = os.getenv('GPT5_VISION_MODEL', 'gpt-5.1')

    try:
        client = OpenAI(api_key=api_key)

        # Optimize image if needed
        optimized_path = _optimize_image_for_api(image_path)

        # Read and encode image
        with open(optimized_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')

        # Correct API structure for GPT-5 Responses API
        response = client.responses.create(
            model=model,
            input=[
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt or "Analyze this financial/business image. Extract all text, numbers, tables, and key information."},
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_base64}"}
                    ]
                }
            ]
        )

        # Clean up temp file if created
        if optimized_path != image_path and os.path.exists(optimized_path):
            os.remove(optimized_path)

        # Extract text from response
        # GPT-5 response.output is a list: [reasoning_item, message_item]
        # Text is in message_item.content[0].text
        analysis_text = ""
        if hasattr(response, 'output') and isinstance(response.output, list):
            for item in response.output:
                # Look for message items with content
                if hasattr(item, 'content') and item.content:
                    for content_item in item.content:
                        if hasattr(content_item, 'text'):
                            analysis_text += content_item.text

        if not analysis_text:
            # Fallback to string representation
            analysis_text = str(response)

        return {
            "success": True,
            "analysis": analysis_text.strip(),
            "model": model
        }

    except Exception as e:
        logger.error(f"GPT-5 vision error: {e}")
        return {"success": False, "error": str(e)}

def analyze_pdf_with_gpt5(pdf_path: str, page_limit: int = 5) -> Dict[str, Any]:
    """
    Analyze PDF pages as images using GPT-5.
    Renders pages sequentially (fast) then calls GPT in parallel to cut wall time.

    Args:
        pdf_path: Path to PDF file
        page_limit: Max pages to process

    Returns:
        Combined analysis from all pages
    """
    try:
        from openai import OpenAI
        from PIL import Image
    except ImportError as e:
        return {"error": f"Required packages not installed: {e}"}

    # Choose renderer: prefer pdf2image (poppler) if available; fallback to PyMuPDF
    renderer = "fitz"
    try:
        from pdf2image import convert_from_path  # type: ignore
        renderer = "pdf2image"
    except ImportError:
        pass

    # PyMuPDF imports only if needed
    if renderer == "fitz":
        try:
            import fitz  # PyMuPDF
        except ImportError as e:
            return {"error": f"Required packages not installed: {e}"}

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return {"error": "OPENAI_API_KEY not configured"}

    # Get model and page limit from env
    model = os.getenv('GPT5_VISION_MODEL', 'gpt-5.1')
    page_limit = min(page_limit, int(os.getenv('PDF_PAGE_LIMIT', '5')))

    try:
        # Render pages to images
        payloads: List[Tuple[int, str]] = []

        if renderer == "pdf2image":
            images = convert_from_path(
                pdf_path,
                dpi=200,
                first_page=1,
                last_page=min(page_limit, int(os.getenv('PDF_PAGE_LIMIT', '5')))
            )
            for idx, img in enumerate(images):
                if max(img.size) > 2048:
                    img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG", quality=85)
                img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                payloads.append((idx, img_base64))
        else:
            import fitz  # type: ignore
            pdf_document = fitz.open(pdf_path)
            for page_num in range(min(len(pdf_document), page_limit)):
                page = pdf_document[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scale for better quality
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                if max(img.size) > 2048:
                    img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG", quality=85)
                img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                payloads.append((page_num, img_base64))
            pdf_document.close()

        # Parallelize GPT calls
        max_workers = min(len(payloads), int(os.getenv('PDF_VISION_WORKERS', '4')))
        results = []

        def process_page(item: Tuple[int, str]) -> Dict[str, Any]:
            page_num_local, img_b64 = item
            try:
                client_local = OpenAI(api_key=api_key)
                prompt = (
                    f"Analyze page {page_num_local + 1} of this financial document. "
                    f"Extract all text, tables, charts, and key information."
                )
                response = client_local.responses.create(
                    model=model,
                    input=[
                        {
                            "type": "message",
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": prompt},
                                {"type": "input_image", "image_url": f"data:image/jpeg;base64,{img_b64}"}
                            ]
                        }
                    ]
                )

                analysis_text = ""
                if hasattr(response, 'output') and isinstance(response.output, list):
                    for item_out in response.output:
                        if hasattr(item_out, 'content') and item_out.content:
                            for content_item in item_out.content:
                                if hasattr(content_item, 'text'):
                                    analysis_text += content_item.text

                if not analysis_text:
                    analysis_text = "No text extracted"

                return {
                    "page": page_num_local + 1,
                    "analysis": analysis_text.strip()
                }
            except Exception as exc:
                logger.error(f"Error processing page {page_num_local + 1}: {exc}")
                return {"page": page_num_local + 1, "error": str(exc)}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_page = {executor.submit(process_page, p): p[0] for p in payloads}
            for future in as_completed(future_to_page):
                results.append(future.result())

        # Sort results by page number
        results.sort(key=lambda r: r.get("page", 0))

        return {
            "success": True,
            "results": results,
            "pages_processed": len(results),
            "model": model,
            "renderer": renderer
        }

    except Exception as e:
        logger.error(f"PDF processing error: {e}")
        return {"success": False, "error": str(e)}

def _optimize_image_for_api(image_path: str, max_size: int = 2048) -> str:
    """Optimize image size for API if needed."""
    try:
        from PIL import Image
    except ImportError:
        return image_path

    # Get max size from env or use default
    max_size = int(os.getenv('IMAGE_MAX_SIZE', '2048'))

    try:
        img = Image.open(image_path)

        # Check if optimization needed
        if max(img.size) > max_size:
            # Create optimized copy
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Save as JPEG for better compression
            temp_path = f"{image_path}_opt.jpg"

            # Convert RGBA to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img

            img.save(temp_path, "JPEG", quality=85, optimize=True)
            logger.info(f"Optimized image from {max(Image.open(image_path).size)}px to {max(img.size)}px")
            return temp_path

        return image_path

    except Exception as e:
        logger.error(f"Image optimization error: {e}")
        return image_path
