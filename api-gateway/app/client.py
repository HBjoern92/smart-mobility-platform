import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Shared async client – reused across all requests (connection pooling)
_client: httpx.AsyncClient | None = None


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=10.0)
    return _client


async def close_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


async def proxy_get(url: str) -> Any:
    """Forward a GET request and raise HTTPException on upstream errors."""
    client = await get_client()
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Upstream error GET %s: %s", url, e.response.text)
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json())
    except httpx.RequestError as e:
        logger.error("Connection error GET %s: %s", url, e)
        raise HTTPException(status_code=503, detail=f"Upstream service unavailable: {url}")


async def proxy_post(url: str, payload: Dict[str, Any]) -> Any:
    """Forward a POST request and raise HTTPException on upstream errors."""
    client = await get_client()
    try:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Upstream error POST %s: %s", url, e.response.text)
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json())
    except httpx.RequestError as e:
        logger.error("Connection error POST %s: %s", url, e)
        raise HTTPException(status_code=503, detail=f"Upstream service unavailable: {url}")


async def proxy_patch(url: str, payload: Dict[str, Any]) -> Any:
    """Forward a PATCH request and raise HTTPException on upstream errors."""
    client = await get_client()
    try:
        resp = await client.patch(url, json=payload)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Upstream error PATCH %s: %s", url, e.response.text)
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json())
    except httpx.RequestError as e:
        logger.error("Connection error PATCH %s: %s", url, e)
        raise HTTPException(status_code=503, detail=f"Upstream service unavailable: {url}")
