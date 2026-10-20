"""
Tag-oriented operations for the Polymarket service.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .utils import prune_nones, utc_now_iso


async def discover_tags(service, params: Dict[str, Any]) -> Dict[str, Any]:
    slug = params.get("slug", "").strip()
    if not slug:
        raise ValueError("slug is required")

    status = params.get("status", "active")
    include_related = bool(params.get("include_related", False))
    omit_empty = bool(params.get("omit_empty_related", True))
    include_template = bool(params.get("include_template", False))
    refresh = bool(params.get("refresh", False))

    cache_key = service.scoped_cache_key(
        "tag",
        slug,
        status,
        include_related,
        omit_empty,
        include_template,
    )
    if not refresh:
        cached = await service.tag_cache.get(cache_key)
        if cached is not None:
            cached["cache_hit"] = True
            return cached

    tag_query = prune_nones({"include_template": include_template or None})
    tag_payload = await service.client.get_gamma(f"/tags/slug/{slug}", params=tag_query or None)
    tag = tag_payload.json()

    related = []
    related_fields: List[str] = []
    if include_related:
        query = prune_nones({"status": status, "omit_empty": omit_empty})
        related_resp = await service.client.get_gamma(f"/tags/slug/{slug}/related-tags/tags", params=query)
        related = related_resp.json()
        for item in related:
            if isinstance(item, dict):
                related_fields.extend(item.keys())

    result = {
        "slug": slug,
        "tag": tag,
        "fields_seen": sorted(tag.keys()) if isinstance(tag, dict) else [],
        "related_tags": related,
        "related_fields_seen": sorted(set(related_fields)),
        "status_requested": status,
        "timestamp": utc_now_iso(),
        "cache_hit": False,
    }

    await service.tag_cache.set(cache_key, result)
    return result

