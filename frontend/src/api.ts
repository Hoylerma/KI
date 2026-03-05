export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export async function getStatus(): Promise<string> {
  try {
    const response = await fetch(`${API_BASE_URL}/`);
    const data = await response.json();
    return data.status || 'Verbunden';
  } catch {
    return 'Backend nicht erreichbar';
  }
}