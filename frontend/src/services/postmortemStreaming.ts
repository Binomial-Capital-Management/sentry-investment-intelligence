import { StreamingService } from './streaming';
import { API_BASE } from './api';

// Singleton streaming service dedicated to post-mortems (endpoint passed per call)
export const postmortemStreamingService = new StreamingService();

// Helper to build the per-postmortem stream URL
export const getPostmortemStreamEndpoint = (postmortemId: string) =>
  `${API_BASE}/api/postmortem/${postmortemId}/analyze/stream`;
