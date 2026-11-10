import { Button, Dropdown, Tooltip } from 'antd'

export interface ExportItem { key: string; label: string; onClick: () => void }

const Download = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
    strokeLinejoin="round" aria-hidden="true"><path d="M12 3v12m0 0-4-4m4 4 4-4M5 21h14" /></svg>
)

/** Exportação só com ícone: o nome acessível e a dica ficam no rótulo. */
export function ExportMenu({ label, items, loading }: { label: string; items: ExportItem[]; loading?: boolean }) {
  return (
    <Dropdown menu={{ items }} trigger={['click']}>
      <Tooltip title="Exportar">
        <Button className="no-print" type="text" loading={loading} aria-label={label} icon={<Download />}
          style={{ minWidth: 36, height: 36 }} />
      </Tooltip>
    </Dropdown>
  )
}
