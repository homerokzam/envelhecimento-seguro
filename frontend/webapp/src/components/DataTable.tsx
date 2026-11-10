import { Card, Table } from 'antd'
import { ExportMenu } from './ExportMenu'
import { csvDocument, saveText } from '../exportData'
import type { ColumnsType } from 'antd/es/table'
import type { Filters, Item, Metadata } from '../api/types'
import { fmtDec, fmtInt, fmtMoney } from '../format'

const RIGHT = 'right' as const
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
      { title: 'População-ano', align: RIGHT, key: 'p', render: (_: unknown, r: Item) => fmtInt(r.metrics?.population) },
      { title: 'Taxa / 100 mil', align: RIGHT, key: 'r', render: (_: unknown, r: Item) => r.metrics?.rate == null ? 'Taxa indisponível' : fmtDec(r.metrics.rate) },
      { title: 'Taxa padronizada', align: RIGHT, key: 'sr', render: (_: unknown, r: Item) => fmtDec(r.metrics?.standardRate) },
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
    </Card>
  )
}
