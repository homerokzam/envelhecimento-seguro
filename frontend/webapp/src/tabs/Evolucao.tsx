import { Col, Row } from 'antd'
import type { Data, Layout } from 'plotly.js'
import type { Dashboard, Item } from '../api/types'
import { ChartPlot } from '../components/ChartPlot'

const GREEN = '#21816e'
const value = (items: Item[], key: 'admissions' | 'rate') => items.map(i => i.metrics?.[key] ?? null)

/** Faixa 2020–2022 (pandemia), apenas quando está dentro do período. */
export function pandemic(years: number[]): Partial<Layout> {
  if (!years.some(y => y >= 2020 && y <= 2022)) return {}
  return {
    shapes: [{ type: 'rect', xref: 'x', yref: 'paper', x0: 2019.5, x1: 2022.5, y0: 0, y1: 1,
      fillcolor: '#9aa8a6', opacity: 0.18, line: { width: 0 } }],
    annotations: [{ text: 'Pandemia (2020–2022)', xref: 'x', yref: 'paper', x: 2021, y: 1, yanchor: 'bottom',
      showarrow: false, font: { size: 10, color: '#4c6668' } }],
  }
}

export function Evolucao({ data }: { data: Dashboard }) {
  const years = data.series.map(i => +i.key)
  const bars = (items: Item[], key: 'rate'): Data[] => [{ type: 'bar', x: items.map(i => i.label),
    y: value(items, key), marker: { color: GREEN }, hovertemplate: '%{x}: %{y:.1f}<extra></extra>' }]
  const base = { meta: data.metadata, filters: data.filters }
  return (
    <div className="stack" style={{ display: 'grid', gap: 16 }}>
      <ChartPlot {...base} title="Evolução das internações" unit="Internações por ano de processamento" fileName="evolucao"
        data={[{ type: 'bar', x: years, y: value(data.series, 'admissions'), marker: { color: GREEN },
          hovertemplate: '%{x}: %{y:,}<extra></extra>' }]}
        layout={{ ...pandemic(years), xaxis: { dtick: 1 } }} />
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}><ChartPlot {...base} title="Faixa etária" unit="Internações por 100 mil habitantes"
          fileName="faixa-etaria" data={bars(data.ages, 'rate')} /></Col>
        <Col xs={24} lg={12}><ChartPlot {...base} title="Sexo" unit="Internações por 100 mil habitantes"
          fileName="sexo" data={bars(data.sexes, 'rate')} /></Col>
      </Row>
    </div>
  )
}
