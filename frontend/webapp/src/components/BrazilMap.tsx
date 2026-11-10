import { Grid, Select } from 'antd'
import type { Data } from 'plotly.js'
import type { Dashboard } from '../api/types'
import geo from '../assets/br-uf.json'
import { fmtDec } from '../format'
import { useUi } from '../store/ui'
import { ChartPlot } from './ChartPlot'

export function BrazilMap({ data }: { data: Dashboard }) {
  const { indicator, setIndicator, age } = useUi()
  const mobile = !Grid.useBreakpoint().md
  const outline = { color: '#6b8582', width: 0.8 }
  const metric = indicator === 'standardRate' && !age ? 'standardRate' : 'rate'
  const items = data.territories
  const available = items.filter(i => i.metrics?.[metric] != null)
  const hover = (label: string, v: number | null | undefined) =>
    v == null ? `${label}<br>taxa indisponível` : `${label}<br>${fmtDec(v)} por 100 mil`

  const traces: Data[] = [
    // base cinza: UF sem taxa disponível (zero verdadeiro aparece em branco na camada de cima)
    { type: 'choropleth', geojson: geo as never, locations: items.map(i => i.key), z: items.map(() => 0),
      colorscale: [[0, '#c3cccb'], [1, '#c3cccb']], showscale: false, marker: { line: outline },
      text: items.map(i => hover(i.label, i.metrics?.[metric])), hoverinfo: 'text' },
    { type: 'choropleth', geojson: geo as never, locations: available.map(i => i.key),
      z: available.map(i => i.metrics![metric] as number), zmin: 0,
      colorscale: [[0, '#ffffff'], [0.001, '#d6efe8'], [1, '#0b6658']],
      colorbar: mobile
        ? { title: { text: 'por 100 mil' }, orientation: 'h', thickness: 10, len: 0.9, x: 0.5, xanchor: 'center', y: -0.02, yanchor: 'top' }
        : { title: { text: 'por 100 mil' }, thickness: 12 }, marker: { line: outline },
      text: available.map(i => hover(i.label, i.metrics![metric])), hoverinfo: 'text' },
  ]

  return (
    <>
      <div className="map-toolbar" style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, alignItems: 'center', marginBottom: 8 }}>
        <label htmlFor="indicator">Indicador</label>
        <Select id="indicator" value={metric} style={{ minWidth: 200 }} onChange={setIndicator}
          options={age ? [{ value: 'rate', label: 'Taxa específica' }]
            : [{ value: 'rate', label: 'Taxa bruta' }, { value: 'standardRate', label: 'Padronizada por idade' }]} />
      </div>
      <ChartPlot title="Brasil por UF" unit="Internações por 100 mil habitantes" fileName="mapa-uf"
        data={traces} meta={data.metadata} filters={data.filters} height={mobile ? 440 : 520}
        layout={{ paper_bgcolor: '#e3eaee', plot_bgcolor: '#e3eaee',
          geo: { visible: false, bgcolor: '#e3eaee', projection: { type: 'mercator' },
            lonaxis: { range: [-74.5, -34] }, lataxis: { range: [-34.5, 5.5] },
            domain: mobile ? { x: [0, 1], y: [0.1, 1] } : { x: [0.1, 0.9], y: [0, 1] } },
          margin: { t: 10, l: mobile ? 8 : 0, r: mobile ? 8 : 0, b: mobile ? 120 : 90 } }} />
      <p style={{ color: '#4c6668' }}>
        Mais escuro indica maior taxa nesta seleção. Cinza indica taxa indisponível; zero é exibido em branco.
        {age && ' Com uma única faixa etária, a taxa padronizada fica desabilitada.'}
      </p>
    </>
  )
}
