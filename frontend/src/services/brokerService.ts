/**
 * Broker connection service - API wrapper for IBKR integration
 *
 * Handles:
 * - Connecting IBKR accounts with Flex Query credentials
 * - Getting broker connection status
 * - Fetching synced positions
 * - Disconnecting broker accounts
 */

import api from './api'; // Use shared axios instance with auth

export interface IBKRConnectionRequest {
  flex_token: string;
  flex_query_id: string;
  connection_name?: string;
  token_expires_at?: string;
}

export interface BrokerPosition {
  symbol?: string;
  ticker?: string;
  quantity?: number;
  position?: number;
  positionValue?: number;
  marketValue?: number;
  costBasisPrice?: number;
  unrealizedPnL?: number;
  _source?: string;
  _fetched_at?: string;
  [key: string]: any; // Allow dynamic fields from IBKR
}

export interface BrokerConnectionResponse {
  status: string;
  message: string;
  positions?: BrokerPosition[];
  positions_count?: number;
  connection_id?: string;
  portfolio_id?: string;
  portfolio_name?: string;
}

export interface BrokerConnectionStatus {
  connected: boolean;
  broker_type: string;
  status: string;
  last_sync_at?: string;
  error_message?: string;
  token_expires_at?: string;
}

/**
 * Connect IBKR account with Flex Query credentials
 * Auto-creates a portfolio with synced positions
 *
 * @param tokenExpiresAt - Optional expiration date (IBKR tokens generally don't expire)
 */
export async function connectIBKR(
  flexToken: string,
  flexQueryId: string,
  connectionName: string = 'My IBKR Account',
  tokenExpiresAt?: string,
): Promise<BrokerConnectionResponse> {
  const response = await api.post<BrokerConnectionResponse>(
    '/api/brokers/ibkr/connect',
    {
      flex_token: flexToken,
      flex_query_id: flexQueryId,
      connection_name: connectionName,
      token_expires_at: tokenExpiresAt,
    },
  );
  return response.data;
}

/**
 * Get synced positions from IBKR
 * Returns cached data if available (< 6 hours old)
 */
export async function getIBKRPositions(): Promise<BrokerPosition[]> {
  const response = await api.get<BrokerPosition[]>(
    '/api/brokers/ibkr/positions',
  );
  return response.data;
}

/**
 * Get current IBKR connection status
 */
export async function getIBKRStatus(): Promise<BrokerConnectionStatus> {
  const response = await api.get<BrokerConnectionStatus>(
    '/api/brokers/ibkr/status',
  );
  return response.data;
}

/**
 * Disconnect IBKR account and clear cached data
 * Note: Does not delete associated portfolio (CASCADE SET NULL)
 */
export async function disconnectIBKR(): Promise<void> {
  await api.delete('/api/brokers/ibkr/disconnect');
}

/**
 * Validate Flex Token format (24 digits)
 */
export function validateFlexToken(token: string): boolean {
  return /^\d{24}$/.test(token);
}

/**
 * Validate Flex Query ID format (6-10 digits)
 */
export function validateFlexQueryId(queryId: string): boolean {
  return /^\d{6,10}$/.test(queryId);
}
