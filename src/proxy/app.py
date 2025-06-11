from __future__ import annotations
import os
import json
import time
import uuid
import logging
from typing import Any, Dict, List, Optional

import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from ollama import AsyncClient  # Ollama Python SDK
import anthropic  # Add Anthropic import

# ───────────────────────── ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ─────────────────────────
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
OLLAMA_HOST = OLLAMA_API_BASE.removeprefix("http://").removeprefix("https://")

# Anthropic API configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", '')
ANTHROPIC_API_BASE = os.getenv("ANTHROPIC_API_BASE", '')

# ───────────────────────── ЛОГИРОВАНИЕ ─────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ───────────────────────── КЛИЕНТЫ ─────────────────────────
ollama_client = AsyncClient(host=OLLAMA_HOST)

# Initialize Anthropic client if API key is available
anthropic_client = None
if ANTHROPIC_API_KEY:
    anthropic_client = anthropic.Anthropic(
        api_key=ANTHROPIC_API_KEY,
        base_url=ANTHROPIC_API_BASE
    )
else:
    logger.warning("ANTHROPIC_API_KEY not set. Claude models will not be available.")

app = FastAPI()


# ───────────────────────── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ─────────────────────────
async def _list_models() -> List[str]:
    """Возвращает список имён моделей через словарь Pydantic объекта."""
    response = await ollama_client.list()
    names: List[str] = []
    for model_obj in response.models:
        data = model_obj.dict()
        # Попробуем ключи 'name', 'id', 'model'
        model_name = data.get('name') or data.get('id') or data.get('model')
        if model_name:
            names.append(model_name)

    # Add Claude models if Anthropic client is available
    if anthropic_client:
        # Add some Claude models
        names.extend(["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"])

    return names


async def _chat(**kwargs) -> Any:
    """Обёртка над ollama_client.chat с перехватом ошибок."""
    try:
        return await ollama_client.chat(**kwargs)
    except Exception as e:
        logger.exception("Ошибка Ollama: %s", e)
        raise HTTPException(status_code=500, detail=f"Ollama API error: {e}")


async def _claude_chat(model: str, messages: List[Dict[str, str]], temperature: float = 0.7,
                       max_tokens: Optional[int] = None, stream: bool = False) -> Any:
    """Обработка запросов к Claude API."""
    if not anthropic_client:
        raise HTTPException(status_code=500, detail="Anthropic API key not configured")

    try:
        # Convert OpenAI message format to Anthropic format

        # Process streaming and non-streaming requests differently
        if stream:
            return anthropic_client.messages.stream(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or 4096
            )
        else:
            # Run in a thread to avoid blocking
            def run_claude():
                return anthropic_client.messages.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens or 4096
                )

            return await asyncio.to_thread(run_claude)
    except Exception as e:
        logger.exception("Ошибка Anthropic: %s", e)
        raise HTTPException(status_code=500, detail=f"Anthropic API error: {e}")


# ───────────────────────── ENDPOINTS ─────────────────────────
@app.get("/v1/models")
async def list_models():
    """OpenAI‑совместимый список моделей."""
    names = await _list_models()
    return {
        "object": "list",
        "data": [
            {"id": name, "object": "model", "created": int(time.time()),
             "owned_by": "ollama" if "claude" not in name.lower() else "anthropic"}
            for name in names
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI‑совместимый /v1/chat/completions"""
    body = await request.json()
    model: str = body.get("model", "mistral")
    messages: List[Dict[str, str]] = body.get("messages", [])
    temperature: float = body.get("temperature", 0.7)
    stream: bool = body.get("stream", False)
    max_tokens: Optional[int] = body.get("max_tokens")

    # Check if the model is a Claude model
    is_claude_model = "claude" in model.lower()

    if is_claude_model:
        if not anthropic_client:
            raise HTTPException(status_code=400, detail="Claude models not available: API key not configured")

        if stream:
            async def claude_stream_generator():
                try:
                    stream_manager = await _claude_chat(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=True
                    )

                    with stream_manager as stream:
                        for chunk in stream.text_stream:
                            openai_chunk = {
                                "id": f"chatcmpl-{uuid.uuid4().hex}",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": model,
                                "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
                            }
                            yield f"data: {json.dumps(openai_chunk)}\n\n"

                        # Send final chunk with finish_reason
                        final_chunk = {
                            "id": f"chatcmpl-{uuid.uuid4().hex}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model,
                            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                        }
                        yield f"data: {json.dumps(final_chunk)}\n\n"
                        yield "data: [DONE]\n\n"
                except Exception as e:
                    logger.exception("Claude streaming error: %s", e)
                    error_chunk = {
                        "error": {"message": str(e), "type": "server_error"}
                    }
                    yield f"data: {json.dumps(error_chunk)}\n\n"
                    yield "data: [DONE]\n\n"

            return StreamingResponse(claude_stream_generator(), media_type="text/event-stream")
        else:
            # Non-streaming Claude request
            result = await _claude_chat(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )

            # Extract content from Claude response
            content = result.content[0].text if hasattr(result, 'content') and result.content else ""

            # Create OpenAI-compatible response
            openai_response = {
                "id": f"chatcmpl-{uuid.uuid4().hex}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": result.usage.input_tokens if hasattr(result, 'usage') else 0,
                    "completion_tokens": result.usage.output_tokens if hasattr(result, 'usage') else 0,
                    "total_tokens": (result.usage.input_tokens + result.usage.output_tokens) if hasattr(result,
                                                                                                        'usage') else 0
                },
            }
            return openai_response
    else:
        # Original Ollama processing
        ollama_kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                **({"max_tokens": max_tokens} if max_tokens is not None else {}),
            }
        }
        if max_tokens is not None:
            ollama_kwargs["max_tokens"] = max_tokens

        if stream:
            async def event_generator():
                result = await _chat(**ollama_kwargs)
                async for chunk in result:
                    content = chunk.get("message", {}).get("content", "")
                    done = chunk.get("done", False)
                    openai_chunk = {
                        "id": f"chatcmpl-{uuid.uuid4().hex}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [{"index": 0, "delta": {"content": content} if content else {"role": "assistant"},
                                     "finish_reason": "stop" if done else None}],
                    }
                    yield f"data: {json.dumps(openai_chunk)}\n\n"
                    if done:
                        yield "data: [DONE]\n\n"
                        break

            return StreamingResponse(event_generator(), media_type="text/event-stream")

        result = await _chat(**ollama_kwargs)
        content = getattr(result.message, 'content', '')
        openai_response = {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": getattr(result, 'prompt_eval_count', 0),
                      "completion_tokens": getattr(result, 'eval_count', 0),
                      "total_tokens": getattr(result, 'prompt_eval_count', 0) + getattr(result, 'eval_count', 0)},
        }
        return openai_response


@app.get("/health")
async def health_check():
    """Проверка доступности Ollama и Anthropic."""
    status = {"status": "healthy", "services": {}}

    try:
        names = await _list_models()
        status["services"]["ollama"] = "connected"
        status["models_count"] = len(names)
    except Exception as e:
        logger.error("Ollama health-check failed: %s", e)
        status["status"] = "degraded"
        status["services"]["ollama"] = {"status": "error", "message": str(e)}

    # Check Anthropic if configured
    if anthropic_client:
        try:
            # Simple check - we don't actually make an API call
            status["services"]["anthropic"] = "configured"
        except Exception as e:
            logger.error("Anthropic health-check failed: %s", e)
            status["status"] = "degraded"
            status["services"]["anthropic"] = {"status": "error", "message": str(e)}
    else:
        status["services"]["anthropic"] = "not_configured"

    return status