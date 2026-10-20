from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class IntegrationCategory(str, Enum):
    CLOUD = "Cloud"
    DATABASE = "Database Services"
    LLM = "LLMs"
    COMMUNICATOR = "Communicators"
    ACTION = "Actions"
    BROKERAGE = "Brokerage"

class IntegrationStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    COMING_SOON = "coming_soon"

class Integration(BaseModel):
    id: str
    name: str
    description: str
    category: IntegrationCategory
    status: IntegrationStatus = IntegrationStatus.DISCONNECTED
    icon_url: Optional[str] = None
    docs_url: Optional[str] = None
    
    # Detailed info
    long_description: Optional[str] = None
    features: List[str] = Field(default_factory=list)
    supported_file_types: List[str] = Field(default_factory=list)
    setup_guide_url: Optional[str] = None

class MarketplaceResponse(BaseModel):
    integrations: List[Integration]
