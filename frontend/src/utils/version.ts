import api from '@services/api';

let cached: 'v5' | 'v6' | 'unknown' | null = null;

export async function getBackendVersion(): Promise<'v5' | 'v6' | 'unknown'> {
  if (cached) return cached;
  try {
    const res = await api.get('/health');
    const data = res.data || {};
    const ver = (data.version || data.backendVersion || '').toString().toLowerCase();
    if (ver.startsWith('6')) {
      cached = 'v6';
    } else if (ver.startsWith('5')) {
      cached = 'v5';
    } else {
      cached = 'unknown';
    }
  } catch {
    cached = 'unknown';
  }
  return cached;
}
