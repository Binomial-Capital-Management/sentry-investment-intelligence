"""
Pydantic models for Unusual Whales MCP Server.

Defines data structures for:
- Dataset entries and catalogs
- Rate limit configurations  
- Parameter constraints
"""

import re
from typing import Dict, List, Optional, Any
from enum import Enum
from urllib.parse import quote
from pydantic import BaseModel, Field, validator


class UWDatasetClass(str, Enum):
    """Valid dataset classes in the Unusual Whales catalogs."""
    # Options catalog classes
    OPTIONS_FLOW = "options_flow"
    OPTIONS_VOLATILITY = "options_volatility"
    OPTIONS_GREEKS = "options_greeks"
    OPTIONS_ANALYTICS = "options_analytics"
    OPTIONS_REFERENCE = "options_reference"
    OPTIONS_SCREENER = "options_screener"
    OPTIONS_TIMESERIES = "options_timeseries"
    MARKET_SENTIMENT = "market_sentiment"
    
    # Institutional catalog classes
    CONGRESSIONAL = "congressional"
    DARKPOOL = "darkpool"
    INSTITUTIONAL = "institutional"
    INSIDER = "insider"
    ETF = "etf"
    
    # Market catalog classes
    EARNINGS = "earnings"
    SCREENER = "screener"
    MARKET_ANALYTICS = "market_analytics"
    SHORT_INTEREST = "short_interest"


class RateLimitConfig(BaseModel):
    """Rate limiting configuration for a dataset."""
    rps: int = Field(default=5, ge=1, le=100, description="Requests per second")
    burst: int = Field(default=15, ge=1, le=200, description="Burst capacity")


class ParamConstraint(BaseModel):
    """Parameter constraints (min/max values)."""
    min: Optional[int] = None
    max: Optional[int] = None


class UWDatasetEntry(BaseModel):
    """A single dataset entry in the Unusual Whales catalog."""
    dataset: str = Field(..., min_length=1, description="Unique dataset identifier")
    class_: str = Field(..., alias="class", description="Dataset classification")
    discoverable: bool = Field(..., description="Whether dataset is discoverable")
    url: str = Field(..., description="URL template with path parameter placeholders")
    method: str = Field(default="GET", description="HTTP method")
    params_schema: Dict[str, str] = Field(default_factory=dict, description="Parameter schema")
    identifier_param: Optional[str] = Field(None, description="Primary identifier parameter")
    param_defaults: Optional[Dict[str, Any]] = Field(None, description="Default parameter values")
    param_constraints: Optional[Dict[str, ParamConstraint]] = Field(None, description="Parameter constraints")
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig, description="Rate limits")
    cache_ttl: int = Field(default=300, ge=0, description="Cache TTL in seconds")
    notes: Optional[str] = Field(None, description="Human-readable description")

    class Config:
        populate_by_name = True
    
    @validator('url')
    def validate_url_template(cls, v):
        """Ensure URL has proper template structure."""
        if not v.startswith('/'):
            raise ValueError(f"URL must start with /: {v}")
        if '{' in v and '}' not in v:
            raise ValueError(f"Unclosed placeholder in URL: {v}")
        return v
    
    @validator('method')
    def validate_method(cls, v):
        """Ensure HTTP method is valid."""
        allowed = ['GET', 'POST', 'PUT', 'DELETE']
        if v.upper() not in allowed:
            raise ValueError(f"Method must be one of {allowed}: {v}")
        return v.upper()
    
    def substitute_url(self, **kwargs) -> str:
        """Substitute placeholders in URL template with URL-encoded values."""
        url = self.url
        for key, value in kwargs.items():
            placeholder = f"{{{key}}}"
            if placeholder in url:
                encoded_value = quote(str(value), safe='')
                url = url.replace(placeholder, encoded_value)
        return url
    
    def get_path_params(self) -> List[str]:
        """Extract path parameter names from URL template."""
        return re.findall(r'\{(\w+)\}', self.url)
    
    def get_query_params(self) -> Dict[str, str]:
        """Get query parameters (params not in URL path)."""
        path_params = set(self.get_path_params())
        return {k: v for k, v in self.params_schema.items() if k not in path_params}
    
    def get_required_params(self) -> List[str]:
        """Get list of required parameters (no ? suffix in schema)."""
        return [p for p, t in self.params_schema.items() if not t.endswith('?')]
    
    def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and apply defaults to parameters."""
        result = {}
        
        # Apply defaults first
        if self.param_defaults:
            result.update(self.param_defaults)
        
        # Override with user params
        result.update(params)
        
        # Check required params
        for required in self.get_required_params():
            if required not in result:
                raise ValueError(f"Missing required parameter: {required}")
        
        # Apply constraints
        if self.param_constraints:
            for param, value in result.items():
                if param in self.param_constraints and value is not None:
                    constraint = self.param_constraints[param]
                    if isinstance(constraint, dict):
                        constraint = ParamConstraint(**constraint)
                    try:
                        numeric_value = float(value) if isinstance(value, str) else value
                        if constraint.min is not None and numeric_value < constraint.min:
                            raise ValueError(f"{param} must be >= {constraint.min}")
                        if constraint.max is not None and numeric_value > constraint.max:
                            raise ValueError(f"{param} must be <= {constraint.max}")
                    except (TypeError, ValueError) as e:
                        if "must be" in str(e):
                            raise
                        pass
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with 'class' field name."""
        return self.dict(by_alias=True)


class UWCatalog(BaseModel):
    """The complete Unusual Whales Dataset Catalog."""
    version: str = Field(..., description="Catalog version")
    last_updated: str = Field(..., description="Last update date")
    source: str = Field(..., description="Data source description")
    base_url: str = Field(default="https://api.unusualwhales.com", description="API base URL")
    notes: Optional[str] = Field(None, description="Catalog notes")
    enums: Optional[Dict[str, List[str]]] = Field(None, description="Enum definitions")
    datasets: List[UWDatasetEntry] = Field(..., description="List of datasets")
    
    @validator('datasets')
    def validate_unique_datasets(cls, v):
        """Ensure dataset names are unique."""
        names = [d.dataset for d in v]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate dataset names: {set(duplicates)}")
        return v
    
    def get_dataset_count(self) -> Dict[str, int]:
        """Get count of datasets by class."""
        counts = {}
        for dataset in self.datasets:
            counts[dataset.class_] = counts.get(dataset.class_, 0) + 1
        return counts
    
    def get_enum_values(self, enum_name: str) -> List[str]:
        """Get allowed values for an enum parameter."""
        if self.enums and enum_name in self.enums:
            return self.enums[enum_name]
        return []

