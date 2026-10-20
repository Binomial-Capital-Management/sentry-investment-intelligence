"""
Seed Bloomberg Fields into pgvector.

One-time script. Reads bloomberg_fields.json, embeds each entry via
text-embedding-3-small, and inserts into the bloomberg_fields table.

Usage:
  export DATABASE_URL=postgresql://user:pass@host/db
  python scripts/seed_bloomberg_fields.py
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FIELDS_PATH = Path(__file__).resolve().parent.parent / "core" / "agents" / "data" / "bloomberg_fields.json"
EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 50  # OpenAI embedding batch limit


async def embed_batch(client, texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts."""
    resp = await client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [d.embedding for d in resp.data]


async def main():
    from openai import AsyncOpenAI
    import asyncpg

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        logger.error("OPENAI_API_KEY not set")
        sys.exit(1)

    # Load field catalog
    with open(FIELDS_PATH, "r") as f:
        fields = json.load(f)
    logger.info(f"Loaded {len(fields)} fields from {FIELDS_PATH.name}")

    # Build embedding texts: "MNEMONIC: Name. Description"
    texts = [
        f"{f['mnemonic']}: {f['name']}. {f.get('description', '')}"
        for f in fields
    ]

    # Embed in batches
    client = AsyncOpenAI(api_key=openai_key)
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        logger.info(f"Embedding batch {i // BATCH_SIZE + 1}/{(len(texts) + BATCH_SIZE - 1) // BATCH_SIZE} ({len(batch)} fields)")
        embeddings = await embed_batch(client, batch)
        all_embeddings.extend(embeddings)

    assert len(all_embeddings) == len(fields), f"Embedding count mismatch: {len(all_embeddings)} vs {len(fields)}"
    logger.info(f"Embedded all {len(all_embeddings)} fields (dims={len(all_embeddings[0])})")

    # Insert into database
    conn = await asyncpg.connect(database_url)
    try:
        inserted = 0
        for i, (field, embedding) in enumerate(zip(fields, all_embeddings)):
            vec_str = f"[{','.join(map(str, embedding))}]"
            await conn.execute(
                """
                INSERT INTO bloomberg_fields (mnemonic, name, description, category, data_type, embedding)
                VALUES ($1, $2, $3, $4, $5, $6::vector)
                ON CONFLICT (mnemonic) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    category = EXCLUDED.category,
                    data_type = EXCLUDED.data_type,
                    embedding = EXCLUDED.embedding
                """,
                field["mnemonic"],
                field["name"],
                field.get("description", ""),
                field.get("category", ""),
                field.get("data_type", ""),
                vec_str,
            )
            inserted += 1

        logger.info(f"Inserted/updated {inserted} fields into bloomberg_fields table")
    finally:
        await conn.close()

    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
