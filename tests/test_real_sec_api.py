"""
Test SEC Filing through the REAL API endpoint
This is what actually matters - does it work when users use it?
"""

import asyncio
import httpx
import json

async def test_real_api():
    """Test through the actual FastAPI endpoint"""
    
    base_url = "http://localhost:8002"  # FastAPI server
    
    # Test queries that a real user would ask
    queries = [
        "What are the main risk factors in Apple's latest 10-K filing?",
        "Analyze Apple's revenue segments from their most recent annual report",
        "What competitive threats does Apple mention in their SEC filings?"
    ]
    
    async with httpx.AsyncClient() as client:
        for i, query in enumerate(queries, 1):
            print(f"\n{'='*60}")
            print(f"Query {i}: {query}")
            print('='*60)
            
            try:
                # Call the v6 chat endpoint (the real one users would use)
                response = await client.post(
                    f"{base_url}/v6/chat",
                    json={
                        "message": query,
                        "session_id": f"test_{i}",
                        "include_thinking": False
                    },
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"Response: {data.get('response', 'No response')[:500]}...")
                    
                    # Check if it mentions SEC/filing/10-K
                    response_text = str(data.get('response', '')).lower()
                    if any(word in response_text for word in ['sec', 'filing', '10-k', 'annual report']):
                        print("✅ Response appears to reference SEC filings")
                    else:
                        print("⚠️ Response doesn't mention SEC filings")
                        
                else:
                    print(f"❌ Error: Status {response.status_code}")
                    print(f"Response: {response.text}")
                    
            except httpx.ConnectError:
                print("❌ Cannot connect to API. Is the server running?")
                print("Start it with: python app_fastapi.py")
                return False
            except Exception as e:
                print(f"❌ Error: {e}")
    
    return True

if __name__ == "__main__":
    print("Testing SEC Filing integration through REAL API...")
    print("Make sure the server is running: python app_fastapi.py")
    asyncio.run(test_real_api())