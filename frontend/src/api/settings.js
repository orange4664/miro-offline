import service from './index'

/**
 * Get current LLM / Embedding settings (api keys are masked).
 */
export const getSettings = () => {
  return service.get('/api/settings/llm')
}

/**
 * Save settings. Empty fields are kept unchanged.
 * @param {Object} data - { llm:{model,base_url,api_key}, embedding:{provider,model,base_url,api_key,dimension} }
 */
export const saveSettings = (data) => {
  return service.post('/api/settings/llm', data)
}

/**
 * Test a connection before saving.
 * @param {Object} data - { target:'llm'|'embedding', model, base_url, api_key, provider? }
 */
export const testConnection = (data) => {
  return service.post('/api/settings/test', data)
}
