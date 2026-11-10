import { useEffect } from 'react'
import { Alert, Button, Spin, Tabs } from 'antd'
import { errorMessage } from './api/client'
import { exportUrl, useDashboard } from './api/hooks'
import type { Dashboard } from './api/types'
import { DatasetPanel } from './components/DatasetPanel'
import { Filters } from './components/Filters'
import { Kpis } from './components/Kpis'
import { Notes } from './components/Notes'
import { AboutData } from './components/AboutData'
import { useUi, type TabKey } from './store/ui'
import { Evolucao } from './tabs/Evolucao'
import { Impacto } from './tabs/Impacto'
import { Panorama } from './tabs/Panorama'
import { Perfil } from './tabs/Perfil'

export function App() {
  const { start, end, uf, age, sex, tab, setTab, normalizeYears } = useUi()
  const filters = { start, end, uf, age, sex }
  const query = useDashboard(filters)
  const result = query.data
  const data: Dashboard | undefined = result && !result.empty ? result : undefined

  // as listas de ano vêm dos dados; o padrão 2015–2024 se ajusta ao que existe
  useEffect(() => { if (data) normalizeYears(data.options.years) }, [data?.options.years.join(','), normalizeYears])

  const tabs: { key: TabKey; label: string; children: React.ReactNode }[] = data ? [
    { key: 'panorama', label: 'Panorama territorial', children: <Panorama data={data} /> },
    { key: 'evolucao', label: 'Evolução e perfis', children: <Evolucao data={data} /> },
    { key: 'perfil', label: 'Perfil clínico e hospitalar', children: <Perfil data={data} /> },
    { key: 'impacto', label: 'Impacto hospitalar', children: <Impacto data={data} /> },
  ] : []

  return (
    <>
      <header className="hero"><div className="shell">
        <p className="eyebrow">IESB / PROJETO DE PESQUISA</p>
        <h1>Envelhecimento Seguro</h1>
        <p>Internações por quedas em pessoas de 60 anos ou mais</p>
      </div></header>
      <main className="shell">
        <DatasetPanel />
        {query.isError && <Alert type="error" showIcon title="Consulta indisponível" description={errorMessage(query.error)}
          action={<Button onClick={() => query.refetch()}>Tentar novamente</Button>} />}
        {!result && !query.isError && <Spin description="Consultando indicadores…"><div style={{ padding: 48 }} /></Spin>}
        {result?.empty && <Alert type="info" showIcon title="Os indicadores aparecem depois que a base for baixada." />}
        {data && <AboutData metadata={data.metadata} />}
        {(data || (result?.empty)) && <Filters options={data?.options} />}
        {data && <>
          <Tabs activeKey={tab} onChange={k => setTab(k as TabKey)} items={tabs}
            tabBarExtraContent={<Button href={exportUrl(filters)}>Baixar CSV ↓</Button>} />
          {!data.summary && <Alert type="info" showIcon style={{ marginBottom: 8 }} title="Sem dados para os filtros selecionados." />}
          {data.summary?.partial && <Alert type="warning" showIcon style={{ marginBottom: 8 }} title="Cobertura parcial. Taxas populacionais não exibidas." />}
          <Kpis m={data.summary} />
          <Notes data={data} />
          <footer className="foot">{data.metadata.source} · {data.metadata.version} · {data.filters.start}–{data.filters.end}.
            O SIH/SUS não mede medo de cair nem saúde mental após a alta.</footer>
        </>}
      </main>
    </>
  )
}
