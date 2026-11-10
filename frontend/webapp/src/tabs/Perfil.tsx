import { Alert, Card, Col, Row, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { Data } from 'plotly.js'
import type { Dashboard, MunicipalityItem, ProfileDim } from '../api/types'
import { ChartPlot } from '../components/ChartPlot'
import { fmtDec, fmtInt, fmtMoney } from '../format'

const GREEN = '#21816e'
const PALETTE = [GREEN, '#c0762f', '#3b6ea5', '#8a4f9e', '#9aa8a6']
const HOVER = '%{label}<br>%{value:,} internações (%{customdata[0]:.1f}%)<br>' +
  'Mortalidade %{customdata[1]}<br>Permanência %{customdata[2]}<br>Valor médio %{customdata[3]}<extra></extra>'

const pct = (v: number | null) => v == null ? '—' : `${fmtDec(v)}%`

/** Barras de uma dimensão: horizontais para categorias, verticais para mês e dia da semana. */
function DimChart({ dim, base, unit = 'Internações no período' }: { dim: ProfileDim; base: BaseProps; unit?: string }) {
  const items = dim.items
  const horizontal = !dim.ordered
  const labels = items.map(i => i.label)
  const values = items.map(i => i.admissions)
  const custom = items.map(i => [i.share ?? 0, pct(i.mortality), i.meanStay == null ? '—' : `${fmtDec(i.meanStay)} dias`,
    i.meanApproved == null ? '—' : fmtMoney(i.meanApproved)])
  const trace: Data = horizontal
    ? { type: 'bar', orientation: 'h', y: labels, x: values, customdata: custom, marker: { color: GREEN },
        text: items.map(i => pct(i.share)), textposition: 'outside', cliponaxis: false,
        hovertemplate: HOVER.replace('%{label}', '%{y}').replace('%{value:,}', '%{x:,}') }
    : { type: 'bar', x: labels, y: values, customdata: custom, marker: { color: GREEN },
        hovertemplate: HOVER.replace('%{label}', '%{x}').replace('%{value:,}', '%{y:,}') }
  const height = horizontal ? Math.max(300, items.length * 30 + 120) : 340
  return (
    <ChartPlot {...base} title={dim.title} unit={unit} fileName={`perfil-${dim.key}`} height={height} data={[trace]}
      layout={horizontal
        ? { margin: { t: 20, l: 20, r: 60, b: 90 }, yaxis: { autorange: 'reversed', automargin: true },
            xaxis: { automargin: true } }
        : { margin: { t: 20, l: 60, r: 20, b: 90 } }} />
  )
}

interface BaseProps { meta: Dashboard['metadata']; filters: Dashboard['filters'] }

/** Evolução da participação dos 5 maiores grupos de um tipo (lesão ou queda) ao longo dos anos. */
function ShareTrend({ dim, base }: { dim: ProfileDim; base: BaseProps }) {
  const years = Object.keys(dim.items[0]?.byYear ?? {})
  if (years.length < 2) return null
  const totals = years.map(y => dim.items.reduce((sum, i) => sum + (i.byYear?.[y] ?? 0), 0))
  const traces: Data[] = dim.items.slice(0, 5).map((item, n) => ({
    type: 'scatter', mode: 'lines+markers', name: item.label, x: years.map(Number),
    y: years.map((y, k) => totals[k] ? (item.byYear?.[y] ?? 0) / totals[k] * 100 : null),
    line: { color: PALETTE[n] }, connectgaps: false, hovertemplate: '%{x}: %{y:.1f}%<extra>' + item.label + '</extra>',
  }))
  return (
    <ChartPlot {...base} title={`${dim.title}: participação ao longo dos anos`} unit="% das internações do ano"
      fileName={`perfil-${dim.key}-tendencia`} data={traces}
      layout={{ xaxis: { dtick: 1 }, legend: { orientation: 'h', y: 1.18 }, margin: { t: 60, l: 60, r: 20, b: 90 } }} />
  )
}

function Municipios({ data }: { data: Dashboard }) {
  const m = data.municipalities
  if (!m.available) return null
  const columns: ColumnsType<MunicipalityItem> = [
    { title: '#', key: 'n', width: 48, render: (_, __, i) => i + 1 },
    { title: 'Município de residência', key: 'name', render: (_, r) => <><strong>{r.name}</strong> · {r.uf}</> },
    { title: 'Internações', align: 'right', key: 'a', render: (_, r) => fmtInt(r.admissions) },
    { title: 'Participação', align: 'right', key: 's', render: (_, r) => pct(r.share) },
    { title: 'Óbitos', align: 'right', key: 'd', render: (_, r) => fmtInt(r.deaths) },
    { title: 'Mortalidade', align: 'right', key: 'm', render: (_, r) => r.lowVolume ? 'Menos de 20' : pct(r.mortality) },
    { title: 'Permanência', align: 'right', key: 'p', render: (_, r) => r.meanStay == null ? '—' : `${fmtDec(r.meanStay)} dias` },
  ]
  return (
    <Card title={`Municípios com mais internações (${data.filters.uf || 'Brasil'})`}
      extra={<span style={{ color: '#4c6668' }}>{fmtInt(m.withCases)} municípios com casos</span>}>
      <Table size="small" rowKey="code" columns={columns} dataSource={m.top} pagination={false} scroll={{ x: 'max-content' }} />
      <small style={{ display: 'block', marginTop: 8, color: '#4c6668' }}>
        Contagens, não taxas: o ranking acompanha o tamanho da população do município, e a projeção usada não tem população
        municipal. Todas as idades de 60 anos ou mais e os dois sexos; só o período e a UF filtram esta tabela.
      </small>
    </Card>
  )
}

export function Perfil({ data }: { data: Dashboard }) {
  if (!data.profile.available) {
    return <Alert type="info" showIcon title="Perfil clínico e hospitalar ainda não disponível nesta base"
      description="Esta versão da base foi gerada antes das novas dimensões. Use “Atualizar dados” para refazer a carga (leva horas) e liberar tipo de lesão, tipo de queda, mês, atendimento, hospital, raça/cor e municípios." />
  }
  const dims = Object.fromEntries(data.profile.dims.map(d => [d.key, d]))
  const base = { meta: data.metadata, filters: data.filters }
  const chart = (key: string, unit?: string) => dims[key] && <DimChart dim={dims[key]} base={base} unit={unit} />
  const trend = (key: string) => dims[key] && <ShareTrend dim={dims[key]} base={base} />
  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <Alert type="info" showIcon title="Aqui as barras mostram participação, não taxa: não há população por categoria. Os filtros de período, UF, idade e sexo valem para todos os gráficos. Passe o mouse para ver mortalidade, permanência e valor médio de cada grupo; grupos com menos de 20 internações mostram só a contagem." />
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>{chart('injury', 'Lesão no diagnóstico principal')}</Col>
        <Col xs={24} xl={12}>{chart('fall', 'Causa externa W00–W19')}</Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>{trend('injury')}</Col>
        <Col xs={24} xl={12}>{trend('fall')}</Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>{chart('month', 'Internações por mês')}</Col>
        <Col xs={24} lg={12}>{chart('weekday', 'Internações por dia da semana')}</Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>{chart('urgency')}</Col>
        <Col xs={24} lg={12}>{chart('procedure')}</Col>
        <Col xs={24} lg={12}>{chart('uti')}</Col>
        <Col xs={24} lg={12}>{chart('exit')}</Col>
        <Col xs={24} lg={12}>{chart('nature')}</Col>
        <Col xs={24} lg={12}>{chart('race')}</Col>
      </Row>
      <Municipios data={data} />
    </div>
  )
}
