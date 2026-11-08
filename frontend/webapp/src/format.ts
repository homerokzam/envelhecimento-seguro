const integer = new Intl.NumberFormat('pt-BR')
const decimal = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 })
const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

type Value = number | null | undefined
export const fmtInt = (v: Value) => v == null ? '—' : integer.format(v)
export const fmtDec = (v: Value) => v == null ? '—' : decimal.format(v)
export const fmtMoney = (v: Value) => v == null ? '—' : money.format(v)
export const fmtDate = (iso: string) => new Date(iso).toLocaleDateString('pt-BR')
