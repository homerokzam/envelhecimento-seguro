import { Alert, Card, Table } from 'antd'
import { ExportMenu } from '../components/ExportMenu'
import { csvDocument, saveText } from '../exportData'
import type { ColumnsType } from 'antd/es/table'
import type { Data } from 'plotly.js'
import type { Dashboard, MunicipalityItem, ProfileDim } from '../api/types'
import { ChartPlot } from '../components/ChartPlot'
import { fmtDec, fmtInt, fmtMoney } from '../format'

const GREEN = '#21816e'
const PALETTE = [GREEN, '#c0762f', '#3b6ea5', '#8a4f9e', '#9aa8a6']
const HOVER = '%{label}<br>%{value:,} internações (%{customdata[0]:.1f}%)<br>' +
  'Mortalidade %{customdata[1]}<br>Permanência %{customdata[2]}<br>Valor médio %{customdata[3]}<extra></extra>'

/** Quebra rótulos longos em linhas (`<br>`) de até `max` caracteres, só nos espaços. */
const wrap = (text: string, max = 26) => text.split(' ').reduce<string[]>((lines, word) => {
  const last = lines.length - 1
  if (last >= 0 && lines[last].length + word.length + 1 <= max) lines[last] += ' ' + word
  else lines.push(word)
  return lines
}, []).join('<br>')
const short = (text: string, max = 36) => text.length > max ? text.slice(0, max - 1) + '…' : text

const pct = (v: number | null) => v == null ? '—' : `${fmtDec(v)}%`

/** Barras de uma dimensão: horizontais para categorias, verticais para mês e dia da semana. */
function DimChart({ dim, base, unit }: { dim: ProfileDim; base: BaseProps; unit?: string }) {
  const items = dim.items
  const horizontal = !dim.ordered
  unit ??= horizontal ? '% das internações no período' : 'Internações no período'
  const labels = items.map(i => i.label)
  const values = items.map(i => i.admissions)
  const custom = items.map(i => [i.share ?? 0, pct(i.mortality), i.meanStay == null ? '—' : `${fmtDec(i.meanStay)} dias`,
    i.meanApproved == null ? '—' : fmtMoney(i.meanApproved), i.admissions])
  // barras horizontais mostram a participação (%), igual ao rótulo; a contagem fica no hover e no CSV
  const HOVER_H = '%{customdata[5]}<br>%{customdata[4]:,} internações (%{customdata[0]:.1f}%)<br>' +
    'Mortalidade %{customdata[1]}<br>Permanência %{customdata[2]}<br>Valor médio %{customdata[3]}<extra></extra>'
  const trace: Data = horizontal
    ? { type: 'bar', orientation: 'h', y: items.map(i => wrap(i.label)), x: items.map(i => i.share ?? 0),
        customdata: custom.map((c, n) => [...c, labels[n]]), marker: { color: GREEN },
        text: items.map(i => pct(i.share)), textposition: 'outside', cliponaxis: false, hovertemplate: HOVER_H }
    : { type: 'bar', x: labels, y: values, customdata: custom, marker: { color: GREEN },
        hovertemplate: HOVER.replace('%{label}', '%{x}').replace('%{value:,}', '%{y:,}') }
  // cada categoria ocupa o espaço das suas linhas de rótulo
  const rows = items.reduce((sum, i) => sum + Math.max(1, wrap(i.label).split('<br>').length), 0)
  const height = horizontal ? Math.max(300, rows * 17 + items.length * 14 + 100) : 340
  return (
    <ChartPlot {...base} title={dim.title} unit={unit} fileName={`perfil-${dim.key}`} height={height} data={[trace]}
      layout={horizontal
        ? { margin: { t: 20, l: 200, r: 60 }, yaxis: { autorange: 'reversed', automargin: false },
            xaxis: { automargin: true, ticksuffix: '%', rangemode: 'tozero' } }
        : { margin: { t: 20, l: 60, r: 44 } }} />
  )
}

interface BaseProps { meta: Dashboard['metadata']; filters: Dashboard['filters'] }

/** Evolução da participação dos 5 maiores grupos de um tipo (lesão ou queda) ao longo dos anos. */
function ShareTrend({ dim, base }: { dim: ProfileDim; base: BaseProps }) {
  const years = Object.keys(dim.items[0]?.byYear ?? {})
  if (years.length < 2) return null
  const totals = years.map(y => dim.items.reduce((sum, i) => sum + (i.byYear?.[y] ?? 0), 0))
  const traces: Data[] = dim.items.slice(0, 5).map((item, n) => ({
    type: 'scatter', mode: 'lines+markers', name: short(item.label, 22), x: years.map(Number),
    y: years.map((y, k) => totals[k] ? (item.byYear?.[y] ?? 0) / totals[k] * 100 : null),
    line: { color: PALETTE[n] }, connectgaps: false, hovertemplate: '%{x}: %{y:.1f}%<extra>' + item.label + '</extra>',
  }))
  return (
    <ChartPlot {...base} title={`${dim.title}: participação ao longo dos anos`} unit="% das internações do ano"
      fileName={`perfil-${dim.key}-tendencia`} data={traces} height={460}
      layout={{ xaxis: { dtick: 1, ticksuffix: '' }, yaxis: { ticksuffix: '%', rangemode: 'tozero' },
        legend: { orientation: 'h', x: 0, y: 1.02, yanchor: 'bottom', font: { size: 11 } }, margin: { t: 110, l: 60, r: 20 } }} />
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
      extra={<span className="chart-extra"><span style={{ color: '#4c6668' }}>{fmtInt(m.withCases)} municípios com casos</span>
        <ExportMenu label="Exportar tabela de municípios" items={[{ key: 'csv', label: 'Dados (CSV)', onClick: () => saveText(
          `municipios-${data.filters.uf || 'brasil'}-${data.filters.start}-${data.filters.end}.csv`,
          csvDocument('Municípios com mais internações', 'contagens de internações (60+, ambos os sexos)',
            ['codigo_ibge', 'municipio', 'uf', 'internacoes', 'participacao', 'obitos', 'mortalidade', 'permanencia_media_dias'],
            m.top.map(r => [r.code, r.name, r.uf, r.admissions, r.share, r.deaths, r.lowVolume ? '' : r.mortality, r.meanStay]),
            data.metadata, data.filters)) }]} /></span>}>
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
    <div className="stack" style={{ display: 'grid', gap: 16 }}>
      <Alert type="info" showIcon title="Aqui as barras mostram participação, não taxa: não há população por categoria. Os filtros de período, UF, idade e sexo valem para todos os gráficos. Passe o mouse para ver mortalidade, permanência e valor médio de cada grupo; grupos com menos de 20 internações mostram só a contagem." />
      <div className="cols">
        <div>{chart('injury')}</div>
        <div>{chart('fall')}</div>
      </div>
      <div className="cols">
        <div>{trend('injury')}</div>
        <div>{trend('fall')}</div>
      </div>
      <div className="cols">
        <div>{chart('month', 'Internações por mês')}</div>
        <div>{chart('weekday', 'Internações por dia da semana')}</div>
      </div>
      <div className="cols">
        <div>{chart('urgency')}</div>
        <div>{chart('procedure')}</div>
        <div>{chart('uti')}</div>
        <div>{chart('exit')}</div>
        <div>{chart('nature')}</div>
        <div>{chart('race')}</div>
      </div>
      <Municipios data={data} />
    </div>
  )
}
