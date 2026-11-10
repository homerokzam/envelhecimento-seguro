import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { Dashboard, DatasetStatus, EmptyDashboard, Filters } from './types'

export const toParams = (f: Filters) => ({ start: f.start, end: f.end, uf: f.uf, age: f.age, sex: f.sex })
export const exportUrl = (f: Filters) => '/api/export.csv?' + new URLSearchParams(
  Object.entries(toParams(f)).map(([k, v]) => [k, String(v)])).toString()

export function useDashboard(filters: Filters, enabled = true) {
  return useQuery({
    enabled,
    queryKey: ['dashboard', filters],
    queryFn: async () => (await api.get<Dashboard | EmptyDashboard>('/dashboard', { params: toParams(filters) })).data,
    placeholderData: keepPreviousData,
    retry: false,
  })
}

export function useDatasetStatus() {
  return useQuery({
    queryKey: ['dataset-status'],
    queryFn: async () => (await api.get<DatasetStatus>('/dataset/status')).data,
    // consulta o andamento só enquanto há download em curso
    refetchInterval: query => (query.state.data?.job.state === 'running' ? 2000 : false),
  })
}

export function useUpdateDataset() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (opts: { refresh?: boolean; sample?: boolean }) => (await api.post('/dataset/update', opts)).data,
    onSuccess: () => client.invalidateQueries({ queryKey: ['dataset-status'] }),
  })
}

const LOCAL_HOSTS = /^(localhost|127\.0\.0\.1|\[::1\]|.+\.local)$/

/** Execução local: a página foi aberta em localhost E o serviço de análise não roda em container. */
export function useIsLocal() {
  const status = useDatasetStatus().data
  return status?.environment === 'local' && LOCAL_HOSTS.test(window.location.hostname)
}
