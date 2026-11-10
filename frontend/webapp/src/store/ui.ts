import { create } from 'zustand'
import type { Filters } from '../api/types'

export type TabKey = 'panorama' | 'evolucao' | 'perfil' | 'impacto'
export type Indicator = 'rate' | 'standardRate'

interface UiState extends Filters {
  tab: TabKey
  indicator: Indicator
  yearsTouched: boolean  // o usuário escolheu os anos: não expandir sozinho quando chegam anos novos
  setStart: (year: number) => void
  setEnd: (year: number) => void
  setFilter: (key: 'uf' | 'age' | 'sex', value: string) => void
  setTab: (tab: TabKey) => void
  setIndicator: (indicator: Indicator) => void
  normalizeYears: (years: number[]) => void
}

export const useUi = create<UiState>(set => ({
  start: 2015, end: 2024, yearsTouched: false, uf: '', age: '', sex: '', tab: 'panorama', indicator: 'rate',
  // o ano inicial nunca passa do final, e vice-versa
  setStart: year => set(s => ({ start: year, end: Math.max(s.end, year), yearsTouched: true })),
  setEnd: year => set(s => ({ end: year, start: Math.min(s.start, year), yearsTouched: true })),
  setFilter: (key, value) => set({ [key]: value }),
  setTab: tab => set({ tab }),
  setIndicator: indicator => set({ indicator }),
  // ajusta o padrão 2015–2024 aos anos realmente existentes na base
  normalizeYears: years => set(s => {
    if (!years.length) return s
    if (!s.yearsTouched) {  // padrão: todos os anos disponíveis, inclusive os que chegam durante a carga
      const lo = Math.min(...years), hi = Math.max(...years)
      return lo === s.start && hi === s.end ? s : { start: lo, end: hi }
    }
    const near = (y: number) => years.includes(y) ? y : years.reduce((a, b) => Math.abs(b - y) < Math.abs(a - y) ? b : a)
    const start = near(s.start), end = near(s.end)
    return start === s.start && end === s.end ? s : { start: Math.min(start, end), end: Math.max(start, end) }
  }),
}))
