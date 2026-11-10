import type { Data } from 'plotly.js'
import type { Filters, Metadata } from './api/types'
import { fmtDate } from './format'

type Trace = { name?: string; x?: unknown[]; y?: unknown[]; locations?: unknown[]; z?: unknown[]; type?: string }
const cell = (v: unknown) => {
  const text = v == null ? '' : String(v)
  return /[",\n;]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

/** CSV com a mesma proveniência do rodapé das imagens (fonte, versão, filtros, unidade). */
export function csvDocument(title: string, unit: string, header: string[], rows: unknown[][], meta: Metadata, f: Filters) {
  const lines = [
    `# ${title}`, `# fonte: ${meta.source}`, `# versão: ${meta.version} · extraída em ${fmtDate(meta.createdAt)}`,
    `# unidade: ${unit}`, `# filtros: ${f.start}–${f.end} · ${f.uf || 'Brasil'} · ${f.age || '60+'} · ${f.sex || 'Ambos os sexos'}`,
  ]
  return '\ufeff' + [...lines, header.map(cell).join(','), ...rows.map(r => r.map(cell).join(','))].join('\r\n') + '\r\n'
}

/** Linhas (série, categoria, valor) de um gráfico Plotly. A base cinza do mapa (z=0) é só desenho e fica de fora. */
export function chartRows(title: string, data: Data[]) {
  const rows: unknown[][] = []
  const map = (data as Trace[])[0]?.type === 'choropleth' && data.length > 1
  ;(data as Trace[]).forEach((trace, index) => {
    if (map && index === 0) return
    const keys = trace.locations ?? trace.x ?? []
    const values = trace.z ?? trace.y ?? []
    keys.forEach((key, i) => rows.push([trace.name ?? title, key, values[i]]))
  })
  return rows
}

export const chartCsv = (title: string, unit: string, data: Data[], meta: Metadata, f: Filters) =>
  csvDocument(title, unit, ['serie', 'categoria', 'valor'], chartRows(title, data), meta, f)

export function saveText(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }))
  const link = Object.assign(document.createElement('a'), { href: url, download: name })
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
