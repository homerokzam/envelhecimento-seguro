import { Card, Collapse, Descriptions, Tag } from 'antd'
import type { Metadata } from '../api/types'
import { fmtDate } from '../format'

// Causas externas W00–W19 (CID-10, capítulo XX): o "como caiu".
const FALL_CODES: [string, string][] = [
  ['W00', 'mesmo nível, gelo ou neve'], ['W01', 'mesmo nível, escorregão ou tropeção'],
  ['W03', 'mesmo nível, colisão ou empurrão'], ['W05', 'cadeira de rodas'], ['W06', 'cama'],
  ['W07', 'cadeira'], ['W08', 'outro mobiliário'], ['W10', 'escadas e degraus'],
  ['W11–W12', 'escada de mão, andaime'], ['W13', 'edifício ou estrutura'], ['W14–W16', 'árvore, penhasco, mergulho'],
  ['W17', 'outra queda de um nível a outro'], ['W18', 'outra queda no mesmo nível'], ['W19', 'queda sem especificação'],
]

/** O que são estes dados: o que conta como caso, o que não conta e de onde vêm. */
export function AboutData({ metadata: m }: { metadata: Metadata }) {
  const items = [
    {
      key: 'about',
      label: 'Sobre estes dados: o que é uma internação por queda?',
      children: (
        <>
          <Descriptions size="small" column={1} bordered items={[
            { key: 'o', label: 'O que é', children: 'Internações hospitalares pagas pelo SUS cuja causa foi uma queda (CID-10 W00–W19) em pessoas de 60 anos ou mais.' },
            { key: 'm', label: 'Motivo da internação (CID)',
              children: <>O diagnóstico principal é uma <b>lesão</b> (CID-10 S00–T98, por exemplo fratura de fêmur S72 ou traumatismo de crânio S06) e a
                <b> causa</b> é uma queda (W00–W19) registrada em campo secundário. É o mesmo critério da tabela de causas externas do TABNET.</> },
            { key: 'w', label: 'Tipos de queda (W)',
              children: FALL_CODES.map(([code, text]) => <Tag key={code} style={{ marginBottom: 4 }}><b>{code}</b> {text}</Tag>) },
            { key: 'n', label: 'Não entram', children: 'Internação por outro motivo (pneumonia, AVC etc.) com a queda só como informação adicional; AIH de continuação (só AIH tipo 1 conta); idade ignorada; residência no exterior ou inválida. As exclusões aparecem contadas abaixo.' },
            { key: 'u', label: 'Unidade', children: 'Internações (eventos), não pessoas: a mesma pessoa internada duas vezes conta duas vezes. Por UF de residência e ano de processamento da AIH.' },
            { key: 'r', label: 'Recorte', children: '60–69, 70–79 e 80 anos ou mais; sexo feminino, masculino e ignorado (este só em “Ambos”); foco do estudo: 2019 a 2025 (a base guarda desde 2015 para comparação).' },
            { key: 'pf', label: 'Perfil clínico e hospitalar', children: 'Para cada internação a base guarda também o tipo de lesão (diagnóstico principal), o tipo de queda (W), o mês e o dia da semana da internação, o caráter (urgência ou eletiva), o tipo de procedimento (clínico ou cirúrgico), o uso de UTI, o motivo de saída, a natureza jurídica do hospital, a raça/cor e o município de residência. Essas dimensões mostram participação, não taxa, e fecham exatamente com o total de cada estrato.' },
            { key: 'i', label: 'Indicadores', children: 'Internações, taxa por 100 mil habitantes, taxa padronizada por idade (população do Brasil em 2024), óbitos hospitalares e letalidade, permanência média em dias e valor aprovado pelo SUS. Taxas somam numeradores e denominadores; nunca fazem média de taxas. Menos de 20 internações aparece como volume baixo.' },
            { key: 'l', label: 'Limites', children: 'Só rede SUS (não inclui hospitais privados sem SUS); quedas sem internação não aparecem; óbito é só o ocorrido no hospital; o SIH não mede medo de cair nem saúde mental após a alta.' },
          ]} />
          <Descriptions size="small" column={1} bordered style={{ marginTop: 12 }} title="Origem e rastreabilidade" items={[
            { key: 's', label: 'Fonte', children: 'Ministério da Saúde/DATASUS, Sistema de Informações Hospitalares do SUS (SIH/SUS), arquivos RD (AIH reduzida), por UF e mês.' },
            { key: 'p', label: 'População', children: m.populationEdition },
            { key: 'a', label: 'Acesso', children: `PySUS ${m.pysusVersion || ''}`.trim() },
            { key: 'v', label: 'Base', children: `${m.version}, extraída em ${fmtDate(m.createdAt)}` },
            { key: 'c', label: 'Conciliação', children: m.pilotOk ? 'Aprovada: 2024 (Brasil, DF e SP) confere com o TABNET dentro de 1%.' : 'Sem conciliação aprovada com o TABNET.' },
          ]} />
        </>
      ),
    },
  ]
  return <Card size="small" styles={{ body: { padding: 0 } }} style={{ marginBottom: 16 }}><Collapse ghost items={items} /></Card>
}
