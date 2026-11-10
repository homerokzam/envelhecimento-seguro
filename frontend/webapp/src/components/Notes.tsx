import { Alert } from 'antd'
import type { Dashboard } from '../api/types'
import { fmtInt } from '../format'

const LABELS: Record<string, string> = {
  idade_ignorada: 'idade ignorada',
  residencia_invalida_ou_exterior: 'residência no exterior ou inválida',
  ano_invalido: 'ano inválido',
  queda_sem_lesao_principal: 'queda registrada em internação por outro motivo (diagnóstico principal não é lesão)',
}

export function Notes({ data }: { data: Dashboard }) {
  const { metadata: m, filters: f, notes } = data
  const excluded = Object.entries(m.exclusions)
    .filter(([y]) => +y >= f.start && +y <= f.end)
    .flatMap(([, counts]) => Object.entries(counts))
    .reduce<Record<string, number>>((acc, [k, v]) => ({ ...acc, [k]: (acc[k] ?? 0) + v }), {})
  const total = Object.values(excluded).reduce((a, b) => a + b, 0)
  const incomplete = Object.keys(m.incompleteYears)
  return (
    <>
      {m.partialLoad && <Alert type="info" showIcon style={{ marginBottom: 8 }}
        title={`Carga em andamento: já estão disponíveis ${m.years.join(', ')}. Os demais anos aparecem conforme forem concluídos.`} />}
      {!m.pilotOk && !m.partialLoad && <Alert type="warning" showIcon style={{ marginBottom: 8 }} title="Base sem conciliação aprovada com o TABNET." />}
      {incomplete.length > 0 && <Alert type="info" showIcon style={{ marginBottom: 8 }}
        title={`Anos incompletos fora da base: ${incomplete.join(', ')}.`} />}
      <Alert type="info" showIcon style={{ marginBottom: 8 }} title={
        <>Internações são eventos, não pessoas únicas. {notes.ignoredSexAdmissions > 0 &&
          `${fmtInt(notes.ignoredSexAdmissions)} internações com sexo ignorado estão incluídas em “Ambos”, sem população no denominador. `}
          {total > 0 && `${fmtInt(total)} registros excluídos no período (${Object.entries(excluded)
            .map(([k, v]) => `${LABELS[k] ?? k}: ${fmtInt(v)}`).join('; ')}).`}</>} />
    </>
  )
}
