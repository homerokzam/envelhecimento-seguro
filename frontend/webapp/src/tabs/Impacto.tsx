import { Alert, Col, Row } from 'antd'
import type { Data } from 'plotly.js'
import type { Dashboard } from '../api/types'
import { ChartPlot } from '../components/ChartPlot'
import { DataTable } from '../components/DataTable'
import { pandemic } from './Evolucao'

export function Impacto({ data }: { data: Dashboard }) {
  const years = data.series.map(i => +i.key)
  const line = (key: 'meanStay' | 'mortality'): Data[] => [{ type: 'scatter', mode: 'lines+markers', x: years,
    y: data.series.map(i => i.metrics?.[key] ?? null), line: { color: '#21816e' }, connectgaps: false,
    hovertemplate: '%{x}: %{y:.1f}<extra></extra>' }]
  const base = { meta: data.metadata, filters: data.filters }
  const layout = { ...pandemic(years), xaxis: { dtick: 1 } }
  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}><ChartPlot {...base} title="Permanência média" unit="Dias por ano de processamento"
          fileName="permanencia" data={line('meanStay')} layout={layout} /></Col>
        <Col xs={24} lg={12}><ChartPlot {...base} title="Mortalidade hospitalar" unit="% das internações"
          fileName="mortalidade" data={line('mortality')} layout={layout} /></Col>
      </Row>
      <Alert type="info" showIcon title="Valores aprovados em reais nominais. Não representam o custo econômico total da internação. Mortalidade hospitalar não equivale a mortalidade populacional." />
      <DataTable items={data.territories} hospital />
    </div>
  )
}
