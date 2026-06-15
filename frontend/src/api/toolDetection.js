const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export async function createToolDetectionJob(file, options = {}) {
  const sampleSeconds = options.sampleSeconds ?? 2
  const formData = new FormData()
  formData.append('file', file, file.name || 'video.mp4')

  const response = await fetch(`${API_BASE_URL}/api/tool/jobs?sample_seconds=${encodeURIComponent(sampleSeconds)}`, {
    method: 'POST',
    body: formData,
  })

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(payload?.detail || '器械检测请求失败')
  }

  return payload
}

export async function getToolDetectionJob(jobId) {
  const response = await fetch(`${API_BASE_URL}/api/tool/jobs/${encodeURIComponent(jobId)}`)
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(payload?.detail || '器械检测任务查询失败')
  }
  return payload
}
