import { Card, Col, Row, Statistic } from 'antd'
import type { Metrics } from '../api/types'
import { fmtDec, fmtInt } from '../format'

export function Kpis({ m }: { m: Metrics | null }) {
  const items = [
    { title: 'Internações', value: fmtInt(m?.admissions), detail: 'Registros financiados pelo SUS' },
    { title: 'Taxa de internação', value: fmtDec(m?.rate), detail: 'Por 100 mil habitantes' },
    { title: 'Óbitos hospitalares', value: fmtInt(m?.deaths), detail: 'Durante a internação' },
    { title: 'Permanência média', value: fmtDec(m?.meanStay), detail: 'Dias' },
  ]
  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
      {items.map(i => (
        <Col key={i.title} xs={24} sm={12} lg={6}>
          <Card><Statistic title={i.title} value={i.value} styles={{ content: { color: '#0b6658', fontWeight: 700 } }} />
            <small style={{ color: '#4c6668' }}>{i.detail}</small></Card>
        </Col>
      ))}
    </Row>
  )
}
