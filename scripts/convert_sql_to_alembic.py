#!/usr/bin/env python3
"""
Convert existing SQL migration files to Alembic Python migrations.

This script reads all .sql files from the migrations/ directory and generates
corresponding Alembic migration files in alembic/versions/.

Usage:
    python scripts/convert_sql_to_alembic.py
"""

import os
import re
import hashlib
from pathlib import Path
from datetime import datetime


def generate_revision_id(index: int, filename: str) -> str:
    """Generate a unique 12-character revision ID based on index and filename."""
    # Create a hash from the index and filename for reproducibility
    hash_input = f"{index:04d}_{filename}"
    hash_digest = hashlib.md5(hash_input.encode()).hexdigest()
    return hash_digest[:12]


def sanitize_message(filename: str) -> str:
    """Convert filename to a valid migration message."""
    # Remove .sql extension and clean up
    name = filename.replace('.sql', '')
    # Replace underscores with spaces for readability in docstring
    return name


def escape_sql_for_python(sql: str) -> str:
    """Escape SQL content for embedding in Python triple-quoted string."""
    # Replace backslashes first
    sql = sql.replace('\\', '\\\\')
    # Escape triple quotes if they exist
    sql = sql.replace('"""', '\\"\\"\\"')
    return sql


def create_migration_content(
    revision_id: str,
    down_revision: str | None,
    message: str,
    sql_content: str,
    original_filename: str
) -> str:
    """Generate the Alembic migration file content."""
    
    down_revision_str = f'"{down_revision}"' if down_revision else 'None'
    escaped_sql = escape_sql_for_python(sql_content)
    
    return f'''"""
{message}

Revision ID: {revision_id}
Revises: {down_revision if down_revision else 'None'}
Create Date: {datetime.now().isoformat()}

Original SQL file: {original_filename}
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "{revision_id}"
down_revision = {down_revision_str}
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from {original_filename}."""
    op.execute("""
{escaped_sql}
""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
'''


def main():
    # Get project root (parent of scripts/)
    project_root = Path(__file__).parent.parent
    
    migrations_dir = project_root / "migrations"
    alembic_versions_dir = project_root / "alembic" / "versions"
    
    # Ensure alembic/versions exists
    alembic_versions_dir.mkdir(parents=True, exist_ok=True)
    
    # Get all SQL files sorted by name (they're numbered 000_, 001_, etc.)
    sql_files = sorted(migrations_dir.glob("*.sql"))
    
    if not sql_files:
        print("No SQL migration files found in migrations/")
        return
    
    print(f"Found {len(sql_files)} SQL migration files")
    print(f"Output directory: {alembic_versions_dir}")
    print("-" * 60)
    
    previous_revision = None
    created_files = []
    
    for index, sql_file in enumerate(sql_files):
        filename = sql_file.name
        message = sanitize_message(filename)
        
        # Generate revision ID
        revision_id = generate_revision_id(index, filename)
        
        # Read SQL content
        sql_content = sql_file.read_text(encoding='utf-8')
        
        # Generate migration file content
        migration_content = create_migration_content(
            revision_id=revision_id,
            down_revision=previous_revision,
            message=message,
            sql_content=sql_content,
            original_filename=filename
        )
        
        # Create output filename: {index:04d}_{revision}_{slug}.py
        # Extract the numeric prefix and name from original file
        output_filename = f"{index:04d}_{revision_id}_{message.replace(' ', '_')}.py"
        output_path = alembic_versions_dir / output_filename
        
        # Write the migration file
        output_path.write_text(migration_content, encoding='utf-8')
        created_files.append(output_filename)
        
        print(f"[OK] {filename} -> {output_filename}")
        
        # Update previous revision for next iteration
        previous_revision = revision_id
    
    print("-" * 60)
    print(f"Successfully created {len(created_files)} Alembic migrations")
    print(f"\nMigration chain:")
    print(f"  Head revision: {previous_revision}")
    print(f"\nNext steps:")
    print(f"  1. Move SQL files: mkdir migrations_archive && mv migrations/*.sql migrations_archive/")
    print(f"  2. Test migrations: alembic upgrade head")
    print(f"  3. Check history: alembic history")


if __name__ == "__main__":
    main()
