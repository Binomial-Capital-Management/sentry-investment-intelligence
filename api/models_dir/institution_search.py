"""
Institution Search Models
"""
from pydantic import BaseModel


class InstitutionSearchResult(BaseModel):
    """Search result from institution universe"""
    cik: str
    name: str
