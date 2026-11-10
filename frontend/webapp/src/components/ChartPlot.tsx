import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { Card, Spin, message } from 'antd'
import { ExportMenu } from './ExportMenu'
import type { Data, Layout } from 'plotly.js'
import type { Filters, Metadata } from '../api/types'
import { fmtDate } from '../format'
import { chartCsv, saveText } from '../exportData'

// plotly.js completo, carregado só quando um gráfico é exibido
const loadPlotly = () => import('../plotly')
const Plot = lazy(() => loadPlotly().then(m => ({ default: m.Plot })))

interface Props {
  title: string
  unit: string
  fileName: string
  data: Data[]
  layout?: Partial<Layout>
  meta: Metadata
  filters: Filters
  height?: number
}

/** Rodapé com fonte, versão, data, unidade e filtros: também sai no PNG exportado. */
/** Quebra o texto em linhas de até `max` caracteres, só nos espaços (rodapé em tela estreita). */
function wrap(text: string, max: number) {
  const lines: string[] = []
  for (const word of text.split(' ')) {
    const last = lines.length - 1
    if (last >= 0 && lines[last].length + word.length + 1 <= max) lines[last] += ' ' + word
    else lines.push(word)
  }
  return lines.join('<br>')
}

export function footerText(meta: Metadata, f: Filters, unit: string, compact = false) {
  const sep = compact ? '<br>' : ' · '
  const scope = [f.uf || 'Brasil', f.age || '60+', f.sex || 'Ambos os sexos'].join(' · ')
  const source = compact ? wrap(meta.source, 44) : meta.source
  return `${source}${sep}versão ${meta.version}${sep}extraída em ${fmtDate(meta.createdAt)}<br>` +
    `${unit}${sep}${f.start}–${f.end}${sep}${scope}`
}

export function ChartPlot({ title, unit, fileName, data, layout, meta, filters, height = 340 }: Props) {
  // rodapé em várias linhas quando o gráfico é estreito (celular ou meia largura no desktop)
  const box = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(1000)
  useEffect(() => {
    const el = box.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const watch = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)))
    watch.observe(el)
    return () => watch.disconnect()
  }, [])
  const compact = width < 700
  const graph = useRef<HTMLElement | null>(null)
  const stamp = `${filters.start}-${filters.end}${filters.uf ? '-' + filters.uf : ''}`
  const [busy, setBusy] = useState(false)
  // ao imprimir (relatório em PDF) a página muda de largura: redimensionar o gráfico antes e depois
  useEffect(() => {
    const fit = () => { if (graph.current) void loadPlotly().then(m => m.resize(graph.current!)) }
    window.addEventListener('beforeprint', fit)
    window.addEventListener('afterprint', fit)
    return () => { window.removeEventListener('beforeprint', fit); window.removeEventListener('afterprint', fit) }
  }, [])
  const exportPng = async () => {
    if (!graph.current) return
    setBusy(true)
    try { await (await loadPlotly()).downloadImage(graph.current, { filename: `${fileName}-${stamp}`, scale: 2 }) }
    catch { message.error('Não foi possível gerar a imagem.') }
    finally { setBusy(false) }
  }
  const exportCsv = () => saveText(`${fileName}-${stamp}.csv`, chartCsv(title, unit, data, meta, filters))
  const items = [
    { key: 'png', label: 'Imagem (PNG)', onClick: exportPng },
    { key: 'csv', label: 'Dados (CSV)', onClick: exportCsv },
  ]
  const footer = footerText(meta, filters, unit, compact)
  const lines = footer.split('<br>').length
  // margem inferior = altura do rodapé (10px ≈ 12px de linha) + respiro; no desktop mantém 90
  const m = { t: 20, l: compact ? 44 : 60, r: compact ? 12 : 20, b: compact ? 42 + lines * 12 : 90, ...layout?.margin }
  const below = m.b! - (compact ? lines * 12 + 6 : 16)  // do topo do rodapé até a base da área do gráfico
  return (
    <Card title={title} extra={<span className="chart-extra no-print"><span style={{ color: '#4c6668' }}>{unit}</span>
      <ExportMenu label={`Exportar gráfico ${title}`} items={items} loading={busy} /></span>}>
      <div ref={box} style={{ width: '100%' }}>
      <Suspense fallback={<div style={{ height, display: 'grid', placeItems: 'center' }}><Spin /></div>}>
        <Plot
          data={data}
          layout={{
            autosize: true, height, margin: m,
            font: { family: 'inherit', color: '#143536' }, paper_bgcolor: '#fff', plot_bgcolor: '#fff',
            annotations: [{ text: footer, xref: 'paper', yref: 'paper', x: 0, y: -below / (height - m.t! - m.b!),
              xanchor: 'left', yanchor: 'top', showarrow: false, align: 'left', font: { size: 10, color: '#4c6668' } },
            ...(layout?.annotations ?? [])],
            ...layout, margin: m,
          }}
          config={{ displaylogo: false, responsive: true,
            toImageButtonOptions: { format: 'png', filename: fileName, scale: 2 },
            modeBarButtonsToRemove: ['select2d', 'lasso2d'] }}
          useResizeHandler
          onInitialized={(_, el) => { graph.current = el }}
          onUpdate={(_, el) => { graph.current = el }}
          style={{ width: '100%' }}
        />
      </Suspense>
      </div>
    </Card>
  )
}
