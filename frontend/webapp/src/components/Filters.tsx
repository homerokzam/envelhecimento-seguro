import { Select } from 'antd'
import type { Dashboard } from '../api/types'
import { useUi } from '../store/ui'

const field = (label: string, node: React.ReactNode) => (
  <label style={{ display: 'grid', gap: 4, fontWeight: 600, minWidth: 150, flex: 1 }}>{label}{node}</label>
)

export function Filters({ options }: { options?: Dashboard['options'] }) {
  const { start, end, uf, age, sex, setStart, setEnd, setFilter } = useUi()
  const years = options?.years ?? [start, end]
  const opt = (values: number[]) => values.map(y => ({ value: y, label: String(y) }))
  return (
    <section aria-label="Filtros da análise" style={{ display: 'flex', flexWrap: 'wrap', gap: 16, margin: '16px 0' }}>
      {field('Ano inicial', <Select value={start} onChange={setStart} options={opt(years.filter(y => y <= end))} />)}
      {field('Ano final', <Select value={end} onChange={setEnd} options={opt(years.filter(y => y >= start))} />)}
      {field('Residência', <Select value={uf} onChange={v => setFilter('uf', v)}
        options={[{ value: '', label: 'Brasil' }, ...Object.entries(options?.states ?? {}).map(([value, label]) => ({ value, label }))]} />)}
      {field('Faixa etária', <Select value={age} onChange={v => setFilter('age', v)}
        options={[{ value: '', label: '60 anos ou mais' }, ...(options?.ages ?? []).map(a => ({ value: a, label: a }))]} />)}
      {field('Sexo', <Select value={sex} onChange={v => setFilter('sex', v)}
        options={[{ value: '', label: 'Ambos' }, { value: 'F', label: 'Feminino' }, { value: 'M', label: 'Masculino' }]} />)}
    </section>
  )
}
