// Empty string = relative URL → goes through Next.js rewrite proxy to backend
const API_URL = typeof window !== 'undefined' ? '' : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000');

async function apiFetch(path: string, options: RequestInit = {}) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('token');
      window.location.href = '/auth/login';
    }
    throw new Error('Сессия истекла');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Ошибка сервера' }));
    throw new Error(err.detail || 'Ошибка запроса');
  }

  return res.json();
}

export const api = {
  // Auth
  register: (data: any) => apiFetch('/api/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: (data: any) => apiFetch('/api/auth/login', { method: 'POST', body: JSON.stringify(data) }),

  // Profile
  getMyProfile: () => apiFetch('/api/profiles/me'),
  getProfile: (id: number) => apiFetch(`/api/profiles/${id}`),
  updateProfile: (data: any) => apiFetch('/api/profiles/me', { method: 'PUT', body: JSON.stringify(data) }),
  analyzeProfile: () => apiFetch('/api/profiles/me/analyze', { method: 'POST' }),
  updateEmbedding: () => apiFetch('/api/profiles/me/update-embedding', { method: 'POST' }),

  // Matching
  findMatches: () => apiFetch('/api/matches/find', { method: 'POST' }),
  getTopMatches: () => apiFetch('/api/matches/top'),
  getAcceptedMatches: () => apiFetch('/api/matches/accepted'),
  getIncomingRequests: () => apiFetch('/api/matches/incoming'),
  getAwaitingMatches: () => apiFetch('/api/matches/awaiting'),
  acceptMatch: (id: number) => apiFetch(`/api/matches/${id}/accept`, { method: 'POST' }),
  dismissMatch: (id: number) => apiFetch(`/api/matches/${id}/dismiss`, { method: 'POST' }),
  getStats: () => apiFetch('/api/matches/stats'),

  // Chat
  getMessages: (userId: number) => apiFetch(`/api/chat/${userId}`),
  sendMessage: (userId: number, content: string) =>
    apiFetch(`/api/chat/${userId}`, { method: 'POST', body: JSON.stringify({ content }) }),
  getConversations: () => apiFetch('/api/chat/conversations/list'),

  // Admin
  getAdminSettings: () => apiFetch('/api/admin/settings'),
  updateAdminSettings: (data: any) => apiFetch('/api/admin/settings', { method: 'POST', body: JSON.stringify(data) }),
};
