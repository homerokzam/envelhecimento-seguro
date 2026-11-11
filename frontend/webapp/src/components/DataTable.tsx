import { Button, Card, Popover, Table } from 'antd'
import { ExportMenu } from './ExportMenu'
import { csvDocument, saveText } from '../exportData'
import type { ColumnsType } from 'antd/es/table'
import type { Filters, Item, Metadata } from '../api/types'
import { fmtDec, fmtInt, fmtMoney } from '../format'

const RIGHT = 'right' as const

const Info = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
    strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" /></svg>
)

/** Título de coluna com explicação: abre por clique, foco ou passagem do mouse (funciona no toque e no teclado). */
function HelpTitle({ text, children }: { text: string; children: React.ReactNode }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      {children}
      <Popover content={<div style={{ maxWidth: 280 }}>{text}</div>} trigger={['hover', 'focus', 'click']} placement="top">
        <Button type="text" size="small" aria-label={`Como ler: ${children}`} icon={<Info />}
          style={{ minWidth: 24, width: 24, height: 24, padding: 0, color: 'inherit', opacity: 0.65 }} />
      </Popover>
    </span>
  )
}

const HELP = {
  population: 'Soma da população de 60 anos ou mais em cada ano do período selecionado (pessoa-ano). É o denominador da taxa: assim, escolher mais anos não aumenta a taxa só por somar mais internações.',
  rate: 'Internações por queda para cada 100 mil idosos-ano: internações ÷ população-ano × 100.000. Permite comparar UFs de tamanhos diferentes. Fica indisponível quando faltam dados no recorte.',
  standard: 'Taxa que a UF teria se tivesse a mesma composição por faixa etária do Brasil em 2024 (60–69, 70–79, 80+). Remove o efeito de uma população mais envelhecida e deixa a comparação justa. Só é calculada sem filtro de idade e com dados completos; caso contrário aparece “—”.',
}
const coverage = (m: Item['metrics']) => !m ? 'Sem dados' : m.partial ? 'Parcial' : m.lowVolume ? 'Menos de 20' : 'Completa'

export function DataTable({ items, hospital, meta, filters }: { items: Item[]; hospital?: boolean; meta: Metadata; filters: Filters }) {
  const columns: ColumnsType<Item> = [
    { title: 'UF', dataIndex: 'label', key: 'uf', fixed: 'left', render: (v: string) => <strong>{v}</strong> },
    { title: 'Internações', align: RIGHT, key: 'adm', render: (_, r) => fmtInt(r.metrics?.admissions) },
    ...(hospital ? [
      { title: 'Óbitos', align: RIGHT, key: 'd', render: (_: unknown, r: Item) => fmtInt(r.metrics?.deaths) },
      { title: 'Mortalidade', align: RIGHT, key: 'mo', render: (_: unknown, r: Item) => r.metrics?.mortality == null ? '—' : fmtDec(r.metrics.mortality) + '%' },
      { title: 'Permanência', align: RIGHT, key: 'ps', render: (_: unknown, r: Item) => r.metrics?.meanStay == null ? '—' : fmtDec(r.metrics.meanStay) + ' dias' },
      { title: 'Valor aprovado', align: RIGHT, key: 'va', render: (_: unknown, r: Item) => r.metrics ? fmtMoney(r.metrics.approved) : '—' },
    ] as ColumnsType<Item> : [
      { title: <HelpTitle text={HELP.population}>População-ano</HelpTitle>, align: RIGHT, key: 'p', render: (_: unknown, r: Item) => fmtInt(r.metrics?.population) },
      { title: <HelpTitle text={HELP.rate}>Taxa / 100 mil</HelpTitle>, align: RIGHT, key: 'r', render: (_: unknown, r: Item) => r.metrics?.rate == null ? 'Taxa indisponível' : fmtDec(r.metrics.rate) },
      { title: <HelpTitle text={HELP.standard}>Taxa padronizada</HelpTitle>, align: RIGHT, key: 'sr', render: (_: unknown, r: Item) => fmtDec(r.metrics?.standardRate) },
    ]),
    { title: 'Cobertura', align: RIGHT, key: 'c', render: (_, r) => coverage(r.metrics) },
  ]
  const title = hospital ? 'Detalhe do impacto por UF' : 'Comparação por unidade federativa'
  // CSV com números puros (sem formatação pt-BR) e cobertura explícita: ausente não vira zero
  const exportCsv = () => {
    const header = hospital
      ? ['uf', 'internacoes', 'obitos', 'mortalidade_percentual', 'permanencia_media_dias', 'valor_aprovado_brl_nominal', 'cobertura']
      : ['uf', 'internacoes', 'populacao_ano', 'taxa_100mil', 'taxa_padronizada_100mil', 'cobertura']
    const rows = items.map(i => {
      const m = i.metrics
      return hospital
        ? [i.label, m?.admissions, m?.deaths, m?.mortality, m?.meanStay, m?.approved, coverage(m)]
        : [i.label, m?.admissions, m?.population, m?.rate, m?.standardRate, coverage(m)]
    })
    saveText(`${hospital ? 'impacto' : 'comparacao'}-uf-${filters.start}-${filters.end}.csv`,
      csvDocument(title, hospital ? 'contagens, % e dias' : 'internações e taxa por 100 mil habitantes', header, rows, meta, filters))
  }
  return (
    <Card title={title} extra={<ExportMenu label={`Exportar tabela ${title}`} items={[{ key: 'csv', label: 'Dados (CSV)', onClick: exportCsv }]} />}>
      <Table size="small" rowKey="key" columns={columns} dataSource={items} pagination={false} scroll={{ x: 'max-content' }} />
      {!hospital && (
        <p style={{ margin: '12px 0 0', fontSize: 13, opacity: 0.75 }}>
          Taxas por 100 mil idosos-ano (60+). A taxa padronizada usa a composição etária do Brasil em 2024 e aparece “—” quando há filtro de idade ou dados incompletos.
        </p>
      )}
    </Card>
  )
}
