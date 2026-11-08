import axios, { isAxiosError } from 'axios'

export const api = axios.create({ baseURL: '/api', timeout: 30000 })

export function errorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return detail
    if (!error.response) return 'Não foi possível conectar ao serviço de análise.'
  }
  return 'Não foi possível consultar os indicadores.'
}
