import { lazy, Suspense } from 'react'
import { Card, Spin } from 'antd'
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
export function footerText(meta: Metadata, f: Filters, unit: string) {
  const scope = [f.uf || 'Brasil', f.age || '60+', f.sex || 'Ambos os sexos'].join(' · ')
  return `${meta.source} · versão ${meta.version} · extraída em ${fmtDate(meta.createdAt)}<br>` +
    `${unit} · ${f.start}–${f.end} · ${scope}`
}

export function ChartPlot({ title, unit, fileName, data, layout, meta, filters, height = 340 }: Props) {
  return (
    <Card title={title} extra={<span style={{ color: '#4c6668' }}>{unit}</span>}>
      <Suspense fallback={<div style={{ height, display: 'grid', placeItems: 'center' }}><Spin /></div>}>
        <Plot
          data={data}
          layout={{
            autosize: true, height, margin: { t: 20, l: 60, r: 20, b: 90 },
            font: { family: 'inherit', color: '#143536' }, paper_bgcolor: '#fff', plot_bgcolor: '#fff',
            annotations: [{ text: footerText(meta, filters, unit), xref: 'paper', yref: 'paper', x: 0, y: -74 / (height - 110),
              xanchor: 'left', yanchor: 'top', showarrow: false, align: 'left', font: { size: 10, color: '#4c6668' } },
            ...(layout?.annotations ?? [])],
            ...layout,
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
