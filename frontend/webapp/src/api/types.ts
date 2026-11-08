export interface Metrics {
  admissions: number
  population: number
  deaths: number
  stay_days: number
  stay_count: number
  approved_cents: number
  rate: number | null
  mortality: number | null
  meanStay: number | null
  approved: number
  lowVolume: boolean
  partial: boolean
  standardRate: number | null
}

export interface Item {
  key: string
  label: string
  metrics: Metrics | null
}

export interface Metadata {
  version: string
  createdAt: string
  source: string
  pysusVersion: string
  populationEdition: string
  caseDefinition: string
  unit: string
  years: number[]
  incompleteYears: Record<string, string>
  exclusions: Record<string, Record<string, number>>
  ignoredSexAdmissions: Record<string, number>
  pilotOk: boolean
}

export interface Filters {
  start: number
  end: number
  uf: string
  age: string
  sex: string
}

export interface Dashboard {
  empty?: false
  metadata: Metadata
  filters: Filters
  options: { years: number[]; states: Record<string, string>; ages: string[]; sexes: string[] }
  notes: { ignoredSexAdmissions: number }
  summary: Metrics | null
  territories: Item[]
  series: Item[]
  ages: Item[]
  sexes: Item[]
}

export interface EmptyDashboard {
  empty: true
  metadata: null
}

export interface JobInfo {
  state: 'idle' | 'running' | 'done' | 'error'
  done: number
  total: number
  stage: string
  error: string | null
  startedAt: number | null
}

export interface DatasetStatus {
  hasData: boolean
  metadata: Metadata | null
  job: JobInfo
  estimatedFiles: number
}
