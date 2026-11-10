import { useEffect, useRef } from 'react'
import { Alert, Button, Card, Progress, Space } from 'antd'
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

  if (!status.data) return status.isError
    ? <Alert type="error" showIcon title="Não foi possível consultar o estado da base." description={errorMessage(status.error)} />
    : null

  const running = job?.state === 'running' || update.isPending
  const percent = job && job.total ? Math.floor(job.done / job.total * 100) : 0
  const start = (refresh: boolean, sample = false) => update.mutate({ refresh, sample })


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
            description={`Os dados reais do SIH/SUS ainda não foram baixados.${local ? " Neste ambiente local, prefira a amostra: dados reais, em poucos minutos." : ""} A carga completa reúne cerca de ${fmtInt(status.data.estimatedFiles)} arquivos mensais por UF, pode levar horas e ocupa alguns GB de disco. O download só começa quando você pedir.`}
            action={<Space orientation="vertical">
              {local && <Button type="primary" onClick={() => start(false, true)} disabled={running}>
                Baixar amostra ({status.data.sampleYears.join(" e ")} · {status.data.sampleUfs.join(", ")}, ~{fmtInt(status.data.sampleFiles)} arquivos)</Button>}
              <Button type={local ? 'default' : 'primary'} onClick={() => start(false)} disabled={running}>
                {local ? 'Baixar base completa' : 'Baixar dados do SUS'}</Button>
            </Space>} />
        )}
        {running && <Progress percent={percent} status="active" format={() => `${fmtInt(job?.done)} de ${fmtInt(job?.total)}`} />}
        {running && <small>{job?.stage}</small>}
        {job?.state === 'error' && <Alert type="error" showIcon title="O download falhou" description={`${job.error} A versão anterior continua ativa.`} />}
        {update.isError && <Alert type="error" showIcon title={errorMessage(update.error)} />}
      </Space>
    </Card>
  )
}
