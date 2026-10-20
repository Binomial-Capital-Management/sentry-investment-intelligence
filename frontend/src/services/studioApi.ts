/**
 * Studio API - Fetch and manage persisted studio artifacts
 */

import axios from 'axios';
import { API_BASE } from './api';
import { getAuthToken } from './authService';
import type { StudioArtifact } from '@/stores/uiStore';

const studioApi = axios.create({
  baseURL: `${API_BASE}/api/v6/studio`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth interceptor
studioApi.interceptors.request.use(async (config) => {
  const token = await getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * Load all artifacts for a session from the database
 */
export async function loadSessionArtifacts(sessionId: string): Promise<StudioArtifact[]> {
  try {
    const response = await studioApi.get(`/artifacts/${sessionId}`);
    const data = response.data;
    
    if (data.status !== 'success' || !data.artifacts) {
      return [];
    }
    
    // Transform database records to StudioArtifact format
    return data.artifacts.map((artifact: any) => ({
      id: artifact.id,
      type: artifact.type,
      title: artifact.title || 'Untitled',
      data: typeof artifact.content === 'string' 
        ? JSON.parse(artifact.content) 
        : artifact.content,
      createdAt: new Date(artifact.created_at),
      sourceCount: artifact.source_note_ids?.length || 0,
      saved: true,
    }));
  } catch (error) {
    console.error('Failed to load studio artifacts:', error);
    return [];
  }
}

/**
 * Delete an artifact from the database
 */
export async function deleteArtifact(artifactId: string): Promise<boolean> {
  try {
    const response = await studioApi.delete(`/artifact/${artifactId}`);
    return response.data.status === 'success';
  } catch (error) {
    console.error('Failed to delete artifact:', error);
    return false;
  }
}

/**
 * Update an artifact's title or content
 */
export async function updateArtifact(
  artifactId: string, 
  updates: { title?: string; content?: any }
): Promise<boolean> {
  try {
    const response = await studioApi.patch(`/artifact/${artifactId}`, updates);
    return response.data.status === 'success';
  } catch (error) {
    console.error('Failed to update artifact:', error);
    return false;
  }
}

export default studioApi;
