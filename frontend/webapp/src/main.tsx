import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider } from 'antd'
import ptBR from 'antd/locale/pt_BR'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App } from './App'
import './style.css'

const client = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false, staleTime: 30_000 } } })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider locale={ptBR} theme={{ token: { colorPrimary: '#0b6658', colorTextBase: '#143536',
      colorBgLayout: '#f3f6f5', borderRadius: 8, fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif' } }}>
      <QueryClientProvider client={client}><App /></QueryClientProvider>
    </ConfigProvider>
  </StrictMode>,
)
