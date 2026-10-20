"""
Comprehensive tests for portfolio stability fixes
Following CODING_RULES.md: Test all critical paths
"""

import asyncio
import pytest
from uuid import uuid4
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

# Test imports
from core.services.portfolio_service import PortfolioService, get_portfolio_service
from core.utils.dto_utils import safe_record_access, row_to_dto, portfolio_row_to_dto
from core.utils.cache_utils import stable_cache_key
from core.utils.context_utils import ContextManager, get_user_id, get_session_id


class TestPortfolioService:
    """Test portfolio service layer with RLS enforcement"""
    
    @pytest.fixture
    def service(self):
        """Create portfolio service instance"""
        return PortfolioService()
    
    @pytest.fixture
    def mock_pg_client(self):
        """Mock PostgreSQL client with RLS support"""
        client = AsyncMock()
        client.acquire_with_user_context = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_list_portfolios_with_rls(self, service, mock_pg_client):
        """Test that list_user_portfolios enforces RLS"""
        user_id = str(uuid4())
        mock_conn = AsyncMock()
        
        # Mock portfolio data
        mock_portfolios = [
            {'id': uuid4(), 'name': 'Default Portfolio', 'is_default': True, 
             'created_at': datetime.now(), 'updated_at': datetime.now()},
            {'id': uuid4(), 'name': 'Tech Portfolio', 'is_default': False,
             'created_at': datetime.now(), 'updated_at': datetime.now()}
        ]
        mock_conn.fetch.return_value = mock_portfolios
        
        mock_pg_client.acquire_with_user_context.return_value.__aenter__.return_value = mock_conn
        
        with patch('core.database.postgres_client.get_postgres_rls_client', return_value=mock_pg_client):
            with patch('core.config.get_config') as mock_config:
                mock_config.return_value.enable_postgres = True
                
                result = await service.list_user_portfolios(user_id)
        
        # Verify RLS context was used
        mock_pg_client.acquire_with_user_context.assert_called_once_with(user_id)
        assert result['status'] == 'success'
        assert result['count'] == 2
        assert result['default_portfolio_id'] == str(mock_portfolios[0]['id'])
    
    @pytest.mark.asyncio
    async def test_portfolio_disambiguation(self, service, mock_pg_client):
        """Test name-based portfolio disambiguation"""
        user_id = str(uuid4())
        mock_conn = AsyncMock()
        
        # Multiple portfolios with same name
        duplicate_portfolios = [
            {'id': uuid4(), 'name': 'My Portfolio', 'tickers': ['AAPL'], 'weights': [1.0],
             'created_at': datetime.now(), 'updated_at': datetime.now()},
            {'id': uuid4(), 'name': 'My Portfolio', 'tickers': ['GOOGL'], 'weights': [1.0],
             'created_at': datetime.now(), 'updated_at': datetime.now()}
        ]
        
        mock_conn.fetchrow.return_value = None  # No UUID match
        mock_conn.fetch.return_value = duplicate_portfolios  # Name match returns multiple
        
        mock_pg_client.acquire_with_user_context.return_value.__aenter__.return_value = mock_conn
        
        with patch('core.database.postgres_client.get_postgres_rls_client', return_value=mock_pg_client):
            with patch('core.config.get_config') as mock_config:
                mock_config.return_value.enable_postgres = True
                
                result = await service.get_portfolio(user_id, "My Portfolio")
        
        # Should return error with candidates
        assert result['status'] == 'error'
        assert 'Multiple portfolios' in result['message']
        assert 'candidates' in result
        assert len(result['candidates']) == 2
    
    @pytest.mark.asyncio  
    async def test_active_portfolio_persistence(self, service, mock_pg_client):
        """Test that active portfolio is persisted to database"""
        user_id = str(uuid4())
        session_id = str(uuid4())
        portfolio_id = str(uuid4())
        
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = None  # UPDATE successful
        
        mock_pg_client.acquire_with_user_context.return_value.__aenter__.return_value = mock_conn
        
        # Mock get_portfolio to return valid portfolio
        with patch.object(service, 'get_portfolio') as mock_get:
            mock_get.return_value = {
                'status': 'success',
                'portfolio': {
                    'id': portfolio_id,
                    'name': 'Test Portfolio',
                    'tickers': ['AAPL', 'GOOGL'],
                    'weights': [0.5, 0.5],
                    'value': 1000000
                }
            }
            
            with patch('core.database.postgres_client.get_postgres_rls_client', return_value=mock_pg_client):
                with patch('core.config.get_config') as mock_config:
                    mock_config.return_value.enable_postgres = True
                    
                    result = await service.set_active_portfolio(session_id, user_id, portfolio_id)
        
        # Verify UPDATE was called with correct params
        mock_conn.execute.assert_called_once()
        sql = mock_conn.execute.call_args[0][0]
        assert 'UPDATE chat_sessions' in sql
        assert 'active_portfolio_id' in sql
        
        assert result['status'] == 'success'
        assert result['active_portfolio_id'] == portfolio_id


class TestDTOUtilities:
    """Test DTO conversion utilities for asyncpg.Record handling"""
    
    def test_safe_record_access_dict(self):
        """Test safe access on regular dict"""
        data = {'key1': 'value1', 'key2': 42}
        
        assert safe_record_access(data, 'key1') == 'value1'
        assert safe_record_access(data, 'key2') == 42
        assert safe_record_access(data, 'missing', 'default') == 'default'
    
    def test_safe_record_access_asyncpg_mock(self):
        """Test safe access on asyncpg.Record-like object"""
        # Mock asyncpg.Record behavior
        class MockRecord:
            def __init__(self, data):
                self._data = data
            
            def __getitem__(self, key):
                return self._data[key]
            
            def keys(self):
                return self._data.keys()
        
        record = MockRecord({'id': uuid4(), 'name': 'Test'})
        
        assert safe_record_access(record, 'name') == 'Test'
        assert safe_record_access(record, 'missing', None) is None
    
    def test_row_to_dto_type_conversion(self):
        """Test that row_to_dto properly converts types"""
        test_uuid = uuid4()
        test_datetime = datetime.now()
        
        row = {
            'id': test_uuid,
            'created_at': test_datetime,
            'name': 'Test',
            'tickers': ['AAPL', 'GOOGL'],
            'weights': [0.5, 0.5]
        }
        
        dto = row_to_dto(row)
        
        # UUID should be string
        assert isinstance(dto['id'], str)
        assert dto['id'] == str(test_uuid)
        
        # datetime should be ISO string
        assert isinstance(dto['created_at'], str)
        assert dto['created_at'] == test_datetime.isoformat()
        
        # Lists should remain lists
        assert isinstance(dto['tickers'], list)
        assert dto['tickers'] == ['AAPL', 'GOOGL']
    
    def test_portfolio_row_to_dto_metadata_normalization(self):
        """Test that portfolio DTO normalizes metadata"""
        # Test JSON string metadata
        row1 = {
            'id': uuid4(),
            'name': 'Portfolio 1',
            'tickers': ['AAPL'],
            'metadata': '{"value": 2000000, "currency": "USD"}'
        }
        
        dto1 = portfolio_row_to_dto(row1)
        assert isinstance(dto1['metadata'], dict)
        assert dto1['metadata']['value'] == 2000000
        
        # Test dict metadata (already normalized)
        row2 = {
            'id': uuid4(),
            'name': 'Portfolio 2',
            'tickers': ['GOOGL'],
            'metadata': {'value': 3000000}
        }
        
        dto2 = portfolio_row_to_dto(row2)
        assert isinstance(dto2['metadata'], dict)
        assert dto2['metadata']['value'] == 3000000
        
        # Test missing weights
        row3 = {
            'id': uuid4(),
            'name': 'Portfolio 3',
            'tickers': ['AAPL', 'GOOGL', 'MSFT']
        }
        
        dto3 = portfolio_row_to_dto(row3)
        assert 'weights' in dto3
        assert len(dto3['weights']) == 3
        assert all(w == 1.0/3 for w in dto3['weights'])


class TestCacheUtilities:
    """Test cache key generation with user isolation"""
    
    def test_stable_cache_key_generation(self):
        """Test that cache keys are deterministic and session-based"""
        session_id = str(uuid4())
        
        # Same inputs should produce same key
        key1 = stable_cache_key("intent", session_id, params={'query': 'test'})
        key2 = stable_cache_key("intent", session_id, params={'query': 'test'})
        assert key1 == key2
        
        # Different sessions should have different keys
        other_session_id = str(uuid4())
        key3 = stable_cache_key("intent", other_session_id, params={'query': 'test'})
        assert key1 != key3
        
        # Different params should have different keys
        key4 = stable_cache_key("intent", session_id, params={'query': 'different'})
        assert key1 != key4
    
    def test_cache_key_with_tools(self):
        """Test cache key generation with tool names"""
        session_id = str(uuid4())
        
        key1 = stable_cache_key("risk", session_id, tool="analyze_var_risk")
        key2 = stable_cache_key("risk", session_id, tool="run_monte_carlo")
        
        assert key1 != key2  # Different tools should have different keys


class TestContextUtilities:
    """Test context variable management with proper cleanup"""
    
    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self):
        """Test that context variables are properly cleaned up"""
        user_id = str(uuid4())
        session_id = str(uuid4())
        
        # Before context
        assert get_user_id() is None
        assert get_session_id() is None
        
        # Within context
        async with ContextManager.async_set_context(user_id=user_id, session_id=session_id):
            assert get_user_id() == user_id
            assert get_session_id() == session_id
        
        # After context (should be reset)
        assert get_user_id() is None
        assert get_session_id() is None
    
    @pytest.mark.asyncio
    async def test_context_manager_exception_cleanup(self):
        """Test that context is cleaned up even on exception"""
        user_id = str(uuid4())
        session_id = str(uuid4())
        
        try:
            async with ContextManager.async_set_context(user_id=user_id, session_id=session_id):
                assert get_user_id() == user_id
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Context should still be cleaned up
        assert get_user_id() is None
        assert get_session_id() is None
    
    def test_sync_context_manager(self):
        """Test synchronous context manager"""
        user_id = str(uuid4())
        
        with ContextManager.set_context(user_id=user_id):
            assert get_user_id() == user_id
        
        assert get_user_id() is None


class TestRLSIsolation:
    """Test Row-Level Security isolation between users"""
    
    @pytest.mark.asyncio
    async def test_user_isolation(self):
        """Test that users cannot see each other's data"""
        service = PortfolioService()
        user_a = str(uuid4())
        user_b = str(uuid4())
        
        mock_pg = AsyncMock()
        mock_conn_a = AsyncMock()
        mock_conn_b = AsyncMock()
        
        # User A has portfolios
        mock_conn_a.fetch.return_value = [
            {'id': uuid4(), 'name': 'User A Portfolio', 'is_default': True,
             'created_at': datetime.now(), 'updated_at': datetime.now()}
        ]
        
        # User B has no portfolios (can't see User A's)
        mock_conn_b.fetch.return_value = []
        
        # Setup different connections for different users
        def get_connection(user_id):
            if user_id == user_a:
                return mock_conn_a
            else:
                return mock_conn_b
        
        mock_pg.acquire_with_user_context.side_effect = lambda u: AsyncMock(
            __aenter__=AsyncMock(return_value=get_connection(u)),
            __aexit__=AsyncMock()
        )
        
        with patch('core.database.postgres_client.get_postgres_rls_client', return_value=mock_pg):
            with patch('core.config.get_config') as mock_config:
                mock_config.return_value.enable_postgres = True
                
                # User A sees their portfolio
                result_a = await service.list_user_portfolios(user_a)
                assert result_a['count'] == 1
                
                # User B sees nothing
                result_b = await service.list_user_portfolios(user_b)
                assert result_b['count'] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])