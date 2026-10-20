"""
Institution Search API - Fuzzy search using local institution_universe database
Following CODING_RULES.md: no hardcoding, use pg_trgm for fuzzy matching
Mirrors ticker_search.py pattern
"""
import logging
from fastapi import APIRouter, Query, HTTPException
from typing import List

from api.models_dir.institution_search import InstitutionSearchResult
from core.database.postgres_client import get_postgres_rls_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/institution-search", tags=["institution-search"])


@router.get("", response_model=List[InstitutionSearchResult])
async def search_institutions(
    q: str = Query(..., min_length=1, max_length=100, description="Search query")
):
    """
    Fuzzy search for institutional investors (13F filers) using local database.

    Searches both CIK and institution name fields.
    Returns top 20 matches ranked by similarity score.

    Args:
        q: Search query (CIK number or institution name fragment)

    Returns:
        List of matching institutions with CIK and name
    """
    try:
        pg = await get_postgres_rls_client()

        # Fuzzy search query using pg_trgm similarity + ILIKE for prefix matches
        # Prioritize: exact name match > name prefix > name similarity
        query = """
            SELECT
                cik,
                name,
                CASE
                    WHEN UPPER(name) = UPPER($1) THEN 1000
                    WHEN UPPER(name) LIKE UPPER($1) || '%' THEN 500
                    WHEN UPPER(name_normalized) = UPPER($1) THEN 400
                    WHEN UPPER(name_normalized) LIKE UPPER($1) || '%' THEN 300
                    ELSE (
                        similarity(name, $1) * 60 +
                        similarity(name_normalized, $1) * 40
                    )
                END as score
            FROM institution_universe
            WHERE
                name ILIKE $2
                OR name_normalized ILIKE $2
                OR similarity(name, $1) > 0.1
                OR similarity(name_normalized, $1) > 0.15
            ORDER BY score DESC
            LIMIT 20
        """

        search_pattern = f"%{q}%"

        async with pg.pool.acquire() as conn:
            rows = await conn.fetch(query, q, search_pattern)

        return [
            InstitutionSearchResult(
                cik=r['cik'],
                name=r['name']
            )
            for r in rows
        ]

    except Exception as e:
        logger.error(f"Error searching institutions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search institutions")


@router.get("/by-cik")
async def get_institution_by_cik(
    cik: str = Query(..., description="Institution CIK number")
):
    """
    Get institution details by CIK.

    Args:
        cik: CIK number

    Returns:
        Institution details or 404 if not found
    """
    try:
        pg = await get_postgres_rls_client()

        query = """
            SELECT cik, name, last_updated
            FROM institution_universe
            WHERE cik = $1
        """

        async with pg.pool.acquire() as conn:
            row = await conn.fetchrow(query, cik.strip())

        if not row:
            raise HTTPException(status_code=404, detail="Institution not found")

        return {
            'cik': row['cik'],
            'name': row['name'],
            'last_updated': row['last_updated'].isoformat() if row['last_updated'] else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching institution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch institution")
