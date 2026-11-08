import { Select } from 'antd'
import type { Data } from 'plotly.js'
import type { Dashboard } from '../api/types'
import geo from '../assets/br-uf.json'
import { fmtDec } from '../format'
import { useUi } from '../store/ui'
import { ChartPlot } from './ChartPlot'

export function BrazilMap({ data }: { data: Dashboard }) {
  const { indicator, setIndicator, age } = useUi()
  const metric = indicator === 'standardRate' && !age ? 'standardRate' : 'rate'
  const items = data.territories
  const available = items.filter(i => i.metrics?.[metric] != null)
  const hover = (label: string, v: number | null | undefined) =>
    v == null ? `${label}<br>taxa indisponível` : `${label}<br>${fmtDec(v)} por 100 mil`

  const traces: Data[] = [
    // base cinza: UF sem taxa disponível (zero verdadeiro aparece em branco na camada de cima)
    { type: 'choropleth', geojson: geo as never, locations: items.map(i => i.key), z: items.map(() => 0),
      colorscale: [[0, '#d5dad9'], [1, '#d5dad9']], showscale: false, marker: { line: { color: '#fff', width: 1 } },
      text: items.map(i => hover(i.label, i.metrics?.[metric])), hoverinfo: 'text' },
    { type: 'choropleth', geojson: geo as never, locations: available.map(i => i.key),
      z: available.map(i => i.metrics![metric] as number), zmin: 0,
      colorscale: [[0, '#ffffff'], [0.001, '#d6efe8'], [1, '#0b6658']],
      colorbar: { title: { text: 'por 100 mil' }, thickness: 12 }, marker: { line: { color: '#fff', width: 1 } },
      text: available.map(i => hover(i.label, i.metrics![metric])), hoverinfo: 'text' },
  ]

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, alignItems: 'center', marginBottom: 8 }}>
        <label htmlFor="indicator">Indicador</label>
        <Select id="indicator" value={metric} style={{ width: 220 }} onChange={setIndicator}
          options={age ? [{ value: 'rate', label: 'Taxa específica' }]
            : [{ value: 'rate', label: 'Taxa bruta' }, { value: 'standardRate', label: 'Padronizada por idade' }]} />
      </div>
      <ChartPlot title="Brasil por UF" unit="Internações por 100 mil habitantes" fileName="mapa-uf"
        data={traces} meta={data.metadata} filters={data.filters} height={520}
        layout={{ geo: { visible: false, bgcolor: '#fff', projection: { type: 'mercator' },
          lonaxis: { range: [-74.5, -34] }, lataxis: { range: [-34.5, 5.5] }, domain: { x: [0.1, 0.9], y: [0, 1] } },
          margin: { t: 10, l: 0, r: 0, b: 90 } }} />
      <p style={{ color: '#4c6668' }}>
        Mais escuro indica maior taxa nesta seleção. Cinza indica taxa indisponível; zero é exibido em branco.
        {age && ' Com uma única faixa etária, a taxa padronizada fica desabilitada.'}
      </p>
    </>
  )
}
