import { lazy, Suspense } from 'react'
import { Card, Spin } from 'antd'
import { Grid } from 'antd'
import type { Data, Layout } from 'plotly.js'
import type { Filters, Metadata } from '../api/types'
import { fmtDate } from '../format'

// plotly.js completo, carregado só quando um gráfico é exibido
const Plot = lazy(() => import('react-plotly.js'))

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
  const compact = !Grid.useBreakpoint().md
  const footer = footerText(meta, filters, unit, compact)
  const lines = footer.split('<br>').length
  // margem inferior = altura do rodapé (10px ≈ 12px de linha) + respiro; no desktop mantém 90
  const m = { t: 20, l: compact ? 44 : 60, r: compact ? 12 : 20, b: compact ? 42 + lines * 12 : 90, ...layout?.margin }
  const below = m.b! - (compact ? lines * 12 + 6 : 16)  // do topo do rodapé até a base da área do gráfico
  return (
    <Card title={title} extra={<span style={{ color: '#4c6668' }}>{unit}</span>}>
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
          style={{ width: '100%' }}
        />
      </Suspense>
    </Card>
  )
}
