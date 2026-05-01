import axios from 'axios'

// Session ID stored in localStorage — avoids CORS credential issues entirely
const getSessionId = (): string => {
  if (typeof window === 'undefined') return 'ssr'
  let id = localStorage.getItem('sw_session_id')
  if (!id) {
    id = Math.random().toString(36).slice(2) + Date.now().toString(36)
    localStorage.setItem('sw_session_id', id)
  }
  return id
}

const http = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 120000,
})

// Attach session ID on every request
http.interceptors.request.use(config => {
  config.headers['X-Session-ID'] = getSessionId()
  return config
})

// silent=true → backend skips storing the message in session chat history
// Used for block answers so they don't appear as bubbles in the free chat.
export const sendMessage = (message: string, silent = false) =>
  http.post('/chat', { message, silent }).then(r => r.data)

export const getState = () =>
  http.get('/state').then(r => r.data)

export const getA2AState = () =>
  http.get('/a2a/state').then(r => r.data)

export const sendClarification = (answer: string) =>
  http.post('/a2a/clarification', { answer }).then(r => r.data)

export const toggleSection = (section: string) =>
  http.post('/toggle-section', { section }).then(r => r.data)

export const toggleWhatif = () =>
  http.post('/a2a/toggle-whatif').then(r => r.data)

export const runWhatif = (prompt: string) =>
  http.post('/whatif', { prompt }).then(r => r.data)

export const downloadPdf = () =>
  http.post('/pdf', {}, { responseType: 'blob' }).then(r => r.data)

export const uploadFile = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return http.post('/upload', form).then(r => r.data)
}

export const prefetchBenchmarks = (secteur: string, pays = 'TN') =>
  http.post('/prefetch-benchmarks', { secteur, pays }).then(r => r.data)

export const resetSession = () =>
  http.delete('/reset').then(r => r.data)

export const newConversation = () =>
  http.post('/new-conversation').then(r => r.data)

export const getConversations = () =>
  http.get('/conversations').then(r => r.data)

export const restoreConversation = (id: string) =>
  http.post('/restore-conversation', { conversation_id: id }).then(r => r.data)

export const deleteConversation = (id: string) =>
  http.delete(`/conversations/${id}/delete`).then(r => r.data)
