"""
Unit tests for workspace_tools.py - Agentic AI action tools.

Tests cover:
- add_dataset_to_workspace: Data fetching, caching, rate limiting
- remove_dataset: Action generation
- create_chart: Chart config validation
- create_pivot_table: Pivot config validation
- Context management: set/get/clear workspace context

Note: The @function_tool decorator creates FunctionTool objects, not regular functions.
We test by invoking tools via on_invoke_tool() with JSON input, or by testing
the underlying logic through the module's helper functions.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Import the tools and helpers
from core.agents.tools.workspace_tools import (
    add_dataset_to_workspace,
    remove_dataset,
    create_chart,
    create_pivot_table,
    set_workspace_context,
    get_workspace_context,
    clear_workspace_context,
    WORKSPACE_TOOLS,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def clear_context():
    """Ensure clean context before and after each test."""
    clear_workspace_context()
    yield
    clear_workspace_context()


@pytest.fixture
def mock_user_context():
    """Set up a mock user context."""
    set_workspace_context(
        user_id="test_user_123",
        org_id="test_org_456",
        session_id="test_session_789",
        context_type="workspace",
    )
    return get_workspace_context()


@pytest.fixture
def mock_fmp_data():
    """Sample FMP historical price data."""
    return [
        {"date": "2024-01-05", "open": 185.0, "high": 186.5, "low": 184.0, "close": 185.5, "volume": 50000000},
        {"date": "2024-01-04", "open": 184.0, "high": 185.5, "low": 183.0, "close": 184.5, "volume": 48000000},
        {"date": "2024-01-03", "open": 183.0, "high": 184.0, "low": 182.0, "close": 183.5, "volume": 45000000},
    ]


# =============================================================================
# Helper to invoke FunctionTool
# =============================================================================

async def invoke_tool(tool, **kwargs):
    """
    Invoke a FunctionTool with keyword arguments.
    
    FunctionTool.on_invoke_tool() expects (ctx, input_json_string).
    We create a minimal mock context and pass JSON.
    """
    from unittest.mock import MagicMock
    
    # Create minimal mock context
    mock_ctx = MagicMock()
    mock_ctx.context = MagicMock()
    
    # Convert kwargs to JSON string
    input_json = json.dumps(kwargs)
    
    # Invoke the tool
    result = await tool.on_invoke_tool(mock_ctx, input_json)
    
    # Result might be string or dict depending on tool
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return result
    return result


# =============================================================================
# Context Management Tests
# =============================================================================

class TestContextManagement:
    """Tests for workspace context management using contextvars."""

    def test_set_and_get_context(self):
        """Test setting and retrieving context."""
        set_workspace_context(
            user_id="user_abc",
            org_id="org_xyz",
            session_id="sess_123",
        )
        
        ctx = get_workspace_context()
        assert ctx is not None
        assert ctx["user_id"] == "user_abc"
        assert ctx["org_id"] == "org_xyz"
        assert ctx["session_id"] == "sess_123"
        assert ctx["context_type"] == "workspace"  # default

    def test_clear_context(self):
        """Test clearing context."""
        set_workspace_context(user_id="user_abc")
        assert get_workspace_context() is not None
        
        clear_workspace_context()
        assert get_workspace_context() is None

    def test_process_context_type(self):
        """Test setting process context type."""
        set_workspace_context(
            user_id="user_abc",
            context_type="process",
            process_id="proc_123",
            tool_id="monte_carlo",
        )
        
        ctx = get_workspace_context()
        assert ctx["context_type"] == "process"
        assert ctx["process_id"] == "proc_123"
        assert ctx["tool_id"] == "monte_carlo"


# =============================================================================
# add_dataset_to_workspace Tests
# =============================================================================

class TestAddDatasetToWorkspace:
    """Tests for add_dataset_to_workspace tool."""

    @pytest.mark.asyncio
    async def test_successful_fetch_historical_prices(self, mock_user_context, mock_fmp_data):
        """Test successful fetch of historical price data."""
        # Mock ObjectDataService
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = {"historical-price-full": mock_fmp_data}
        mock_result.errors = []
        mock_result.fetched_at = datetime.now().isoformat()
        
        with patch("core.canvas.object_data_service.ObjectDataService") as MockService:
            mock_service = AsyncMock()
            mock_service.fetch_datasets = AsyncMock(return_value=mock_result)
            MockService.return_value = mock_service
            
            with patch("core.agents.tools.workspace_tools.cache_set") as mock_cache:
                mock_cache.return_value = None
                
                result = await invoke_tool(
                    add_dataset_to_workspace,
                    symbol="AAPL",
                    endpoint="historical-price-full",
                    fields=["date", "close", "volume"],
                )
        
        # Verify success response
        assert result["status"] == "success"
        assert "3 rows" in result["message"]
        assert result["action"]["type"] == "add_dataset"
        assert result["action"]["symbol"] == "AAPL"
        assert result["action"]["endpoint"] == "historical-price-full"
        assert result["action"]["row_count"] == 3

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, mock_user_context):
        """Test rate limiting behavior."""
        with patch("core.agents.tools.workspace_tools.check_rate_limit") as mock_rate:
            mock_rate.return_value = False  # Rate limit exceeded
            
            result = await invoke_tool(
                add_dataset_to_workspace,
                symbol="AAPL",
                endpoint="historical-price-full",
            )
        
        assert result["status"] == "error"
        assert "Rate limit exceeded" in result["message"]
        assert result["code"] == "RATE_LIMIT"

    @pytest.mark.asyncio
    async def test_fetch_no_data_returned(self, mock_user_context):
        """Test handling when no data is returned."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = {"historical-price-full": None}  # No data
        mock_result.errors = []
        mock_result.fetched_at = datetime.now().isoformat()
        
        with patch("core.canvas.object_data_service.ObjectDataService") as MockService:
            mock_service = AsyncMock()
            mock_service.fetch_datasets = AsyncMock(return_value=mock_result)
            MockService.return_value = mock_service
            
            result = await invoke_tool(
                add_dataset_to_workspace,
                symbol="INVALID",
                endpoint="historical-price-full",
            )
        
        assert result["status"] == "error"
        assert "No data found" in result["message"]
        assert result["code"] == "NO_DATA"

    @pytest.mark.asyncio
    async def test_fetch_service_error(self, mock_user_context):
        """Test handling when service returns an error."""
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.data = {}
        mock_result.errors = ["API returned 404"]
        
        with patch("core.canvas.object_data_service.ObjectDataService") as MockService:
            mock_service = AsyncMock()
            mock_service.fetch_datasets = AsyncMock(return_value=mock_result)
            MockService.return_value = mock_service
            
            result = await invoke_tool(
                add_dataset_to_workspace,
                symbol="AAPL",
                endpoint="invalid-endpoint",
            )
        
        assert result["status"] == "error"
        assert "API returned 404" in result["message"]
        assert result["code"] == "FETCH_FAILED"


# =============================================================================
# remove_dataset Tests
# =============================================================================

class TestRemoveDataset:
    """Tests for remove_dataset tool."""

    @pytest.mark.asyncio
    async def test_returns_pending_confirmation(self):
        """Test that remove_dataset returns pending_confirmation status."""
        result = await invoke_tool(remove_dataset, dataset_id="ds-123-abc")
        
        assert result["status"] == "pending_confirmation"
        assert result["action"]["type"] == "remove_dataset"
        assert result["action"]["dataset_id"] == "ds-123-abc"

    @pytest.mark.asyncio
    async def test_generates_action_event(self):
        """Test that action event is properly formatted."""
        result = await invoke_tool(remove_dataset, dataset_id="uuid-test-456")
        
        action = result["action"]
        assert action["type"] == "remove_dataset"
        assert action["dataset_id"] == "uuid-test-456"


# =============================================================================
# create_chart Tests
# =============================================================================

class TestCreateChart:
    """Tests for create_chart tool."""

    @pytest.mark.asyncio
    async def test_successful_line_chart(self):
        """Test creating a valid line chart."""
        result = await invoke_tool(
            create_chart,
            chart_type="line",
            x_axis="date",
            y_series=[{"field": "close", "label": "Price"}],
            title="AAPL Stock Price",
        )
        
        assert result["status"] == "success"
        assert result["action"]["type"] == "create_chart"
        
        config = result["action"]["config"]
        assert config["chartType"] == "line"
        assert config["xAxis"] == "date"
        assert config["ySeries"] == [{"field": "close", "label": "Price"}]
        assert config["title"] == "AAPL Stock Price"

    @pytest.mark.asyncio
    async def test_multiple_y_series(self):
        """Test chart with multiple Y series."""
        y_series = [
            {"field": "close", "label": "Close", "color": "#3b82f6"},
            {"field": "open", "label": "Open", "color": "#ef4444"},
        ]
        
        result = await invoke_tool(
            create_chart,
            chart_type="line",
            x_axis="date",
            y_series=y_series,
        )
        
        assert result["status"] == "success"
        assert len(result["action"]["config"]["ySeries"]) == 2

    @pytest.mark.asyncio
    async def test_invalid_chart_type(self):
        """Test error on invalid chart type."""
        result = await invoke_tool(
            create_chart,
            chart_type="invalid_type",
            x_axis="date",
            y_series=[{"field": "close"}],
        )
        
        assert result["status"] == "error"
        assert result["code"] == "INVALID_CHART_TYPE"

    @pytest.mark.asyncio
    async def test_empty_y_series(self):
        """Test error on empty y_series."""
        result = await invoke_tool(
            create_chart,
            chart_type="line",
            x_axis="date",
            y_series=[],
        )
        
        assert result["status"] == "error"
        assert result["code"] == "INVALID_Y_SERIES"

    @pytest.mark.asyncio
    async def test_y_series_missing_field(self):
        """Test error when y_series item missing 'field' key."""
        result = await invoke_tool(
            create_chart,
            chart_type="line",
            x_axis="date",
            y_series=[{"label": "No Field"}],  # Missing 'field'
        )
        
        assert result["status"] == "error"
        assert "field" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_all_chart_types(self):
        """Test that all valid chart types work."""
        valid_types = ['line', 'area', 'bar', 'scatter', 'candlestick', 'heatmap', 'pie', 'histogram']
        
        for chart_type in valid_types:
            result = await invoke_tool(
                create_chart,
                chart_type=chart_type,
                x_axis="date",
                y_series=[{"field": "value"}],
            )
            assert result["status"] == "success", f"Chart type '{chart_type}' should be valid"

    @pytest.mark.asyncio
    async def test_default_show_legend_and_grid(self):
        """Test default values for showLegend and showGrid."""
        result = await invoke_tool(
            create_chart,
            chart_type="line",
            x_axis="date",
            y_series=[{"field": "close"}],
        )
        
        config = result["action"]["config"]
        assert config["showLegend"] is True
        assert config["showGrid"] is True


# =============================================================================
# create_pivot_table Tests
# =============================================================================

class TestCreatePivotTable:
    """Tests for create_pivot_table tool."""

    @pytest.mark.asyncio
    async def test_successful_pivot(self):
        """Test creating a valid pivot table."""
        result = await invoke_tool(
            create_pivot_table,
            rows=["symbol"],
            columns=["year"],
            values=[{"field": "revenue", "aggregation": "sum"}],
        )
        
        assert result["status"] == "success"
        assert result["action"]["type"] == "create_pivot"
        
        config = result["action"]["config"]
        assert config["rows"] == ["symbol"]
        assert config["columns"] == ["year"]
        assert config["values"] == [{"field": "revenue", "aggregation": "sum"}]

    @pytest.mark.asyncio
    async def test_multiple_values(self):
        """Test pivot with multiple value aggregations."""
        result = await invoke_tool(
            create_pivot_table,
            rows=["sector"],
            columns=[],
            values=[
                {"field": "revenue", "aggregation": "sum"},
                {"field": "price", "aggregation": "avg"},
                {"field": "volume", "aggregation": "max"},
            ],
        )
        
        assert result["status"] == "success"
        assert len(result["action"]["config"]["values"]) == 3

    @pytest.mark.asyncio
    async def test_empty_values_error(self):
        """Test error on empty values list."""
        result = await invoke_tool(
            create_pivot_table,
            rows=["symbol"],
            columns=[],
            values=[],
        )
        
        assert result["status"] == "error"
        assert result["code"] == "INVALID_VALUES"

    @pytest.mark.asyncio
    async def test_invalid_aggregation(self):
        """Test error on invalid aggregation function."""
        result = await invoke_tool(
            create_pivot_table,
            rows=["symbol"],
            columns=[],
            values=[{"field": "revenue", "aggregation": "invalid_agg"}],
        )
        
        assert result["status"] == "error"
        assert result["code"] == "INVALID_AGGREGATION"

    @pytest.mark.asyncio
    async def test_all_aggregation_types(self):
        """Test all valid aggregation types."""
        valid_aggs = ['none', 'sum', 'avg', 'count', 'min', 'max', 'median', 'stddev', 'first', 'last']
        
        for agg in valid_aggs:
            result = await invoke_tool(
                create_pivot_table,
                rows=["x"],
                columns=[],
                values=[{"field": "y", "aggregation": agg}],
            )
            assert result["status"] == "success", f"Aggregation '{agg}' should be valid"

    @pytest.mark.asyncio
    async def test_value_missing_field(self):
        """Test error when value config missing 'field' key."""
        result = await invoke_tool(
            create_pivot_table,
            rows=["x"],
            columns=[],
            values=[{"aggregation": "sum"}],  # Missing 'field'
        )
        
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_value_missing_aggregation(self):
        """Test error when value config missing 'aggregation' key."""
        result = await invoke_tool(
            create_pivot_table,
            rows=["x"],
            columns=[],
            values=[{"field": "revenue"}],  # Missing 'aggregation'
        )
        
        assert result["status"] == "error"


# =============================================================================
# Tool Registration Tests
# =============================================================================

class TestToolRegistration:
    """Tests for tool registration and metadata."""

    def test_workspace_tools_list(self):
        """Test that WORKSPACE_TOOLS contains all expected tools."""
        tool_names = [t.name for t in WORKSPACE_TOOLS]
        
        assert "add_dataset_to_workspace" in tool_names
        assert "remove_dataset" in tool_names
        assert "create_chart" in tool_names
        assert "create_pivot_table" in tool_names

    def test_tools_have_valid_schema(self):
        """Test that all tools have valid JSON schema."""
        for tool in WORKSPACE_TOOLS:
            assert hasattr(tool, 'params_json_schema')
            schema = tool.params_json_schema
            assert isinstance(schema, dict)
            assert 'properties' in schema or 'type' in schema

    def test_tool_count(self):
        """Test expected number of workspace tools."""
        assert len(WORKSPACE_TOOLS) == 4
