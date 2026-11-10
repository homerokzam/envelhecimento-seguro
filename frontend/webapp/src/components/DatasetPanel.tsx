import { useEffect, useRef } from 'react'
import { Alert, Button, Card, Progress, Space, Tag } from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import { errorMessage } from '../api/client'
import { useDatasetStatus, useIsLocal, useUpdateDataset } from '../api/hooks'
import { fmtDate, fmtInt } from '../format'

/** Estado da base: baixar na primeira vez, atualizar depois, com andamento do job. */
export function DatasetPanel() {
  const status = useDatasetStatus()
  const local = useIsLocal()
  const update = useUpdateDataset()
  const client = useQueryClient()
  const job = status.data?.job
  const previous = useRef(job?.state)

  // ao terminar um download, os indicadores são consultados de novo
  useEffect(() => {
    if (previous.current === 'running' && job?.state === 'done') client.invalidateQueries({ queryKey: ['dashboard'] })
    previous.current = job?.state
  }, [job?.state, client])

  // a cada ano concluído o servidor ativa uma versão nova: atualizar os indicadores já
  const version = status.data?.metadata?.version
  const lastVersion = useRef(version)
  useEffect(() => {
    if (lastVersion.current && version && version !== lastVersion.current) client.invalidateQueries({ queryKey: ['dashboard'] })
    lastVersion.current = version
  }, [version, client])

  if (!status.data) return status.isError
    ? <Alert type="error" showIcon title="Não foi possível consultar o estado da base." description={errorMessage(status.error)} />
    : null

  const running = job?.state === 'running' || update.isPending
  const percent = job && job.total ? Math.floor(job.done / job.total * 100) : 0
  const start = (refresh: boolean) => update.mutate({ refresh, sample: local })  // local: sempre a amostra


  return (
    <Card size="small" style={{ marginBottom: 16 }}>
      <Space orientation="vertical" style={{ width: '100%' }}>
        {status.data.hasData && status.data.metadata ? (
          <Space wrap style={{ justifyContent: 'space-between', width: '100%' }}>
            <span>Base {status.data.metadata.version} · extraída em {fmtDate(status.data.metadata.createdAt)} · {status.data.metadata.source}</span>
            <Button onClick={() => start(true)} disabled={running}>Atualizar dados</Button>
          </Space>
        ) : (
          <Alert type="warning" showIcon title="Nenhuma base carregada"
            description={local
              ? `Ambiente local: baixa só uma amostra real do SIH/SUS (${status.data.sampleYears.join(' e ')} · ${status.data.sampleUfs.join(', ')}, cerca de ${fmtInt(status.data.sampleFiles)} arquivos, alguns minutos). A base completa fica para o servidor.`
              : `Os dados reais do SIH/SUS ainda não foram baixados. A carga completa reúne cerca de ${fmtInt(status.data.estimatedFiles)} arquivos mensais por UF, pode levar horas e ocupa alguns GB de disco. O download só começa quando você pedir.`}
            action={<Button type="primary" onClick={() => start(false)} disabled={running}>
              {local ? 'Baixar amostra' : 'Baixar dados do SUS'}</Button>} />
        )}
        {running && <Progress percent={percent} status="active" format={() => `${fmtInt(job?.done)} de ${fmtInt(job?.total)}`} />}
        {running && job?.year && (
          <Space orientation="vertical" size={4}>
            <span><strong>Ano {job.year}</strong>
              {job.yearsDone && job.yearsDone.length > 0 && ` · já disponíveis: ${job.yearsDone.join(', ')}`}</span>
            <Space size={[4, 4]} wrap>
              {(job.finished ?? []).map(uf => <Tag key={uf} color="success">{uf}</Tag>)}
              {(job.running ?? []).map(uf => <Tag key={uf} color="processing">{uf}</Tag>)}
            </Space>
            <small>{(job.finished ?? []).length} UF(s) concluída(s) neste ano · {(job.running ?? []).length} em leitura</small>
          </Space>
        )}
        {running && !job?.year && <small>{job?.stage}</small>}
        {job?.state === 'error' && <Alert type="error" showIcon title="O download falhou" description={`${job.error} A versão anterior continua ativa.`} />}
        {update.isError && <Alert type="error" showIcon title={errorMessage(update.error)} />}
      </Space>
    </Card>
  )
}
