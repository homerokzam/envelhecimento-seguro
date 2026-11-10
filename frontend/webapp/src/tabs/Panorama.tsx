import type { Dashboard } from '../api/types'
import { BrazilMap } from '../components/BrazilMap'
import { DataTable } from '../components/DataTable'

export function Panorama({ data }: { data: Dashboard }) {
  return (
    <div className="stack" style={{ display: 'grid', gap: 16 }}>
      <BrazilMap data={data} />
      <DataTable items={data.territories} />
    </div>
  )
}
