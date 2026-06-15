const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export async function askDoubao(question, context = {}) {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      question,
      context,
    }),
  })

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(payload?.detail || '智能问答请求失败')
  }

  return payload?.answer || ''
}
