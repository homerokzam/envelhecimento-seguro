// Uma única instância do Plotly: monta o componente e expõe a exportação de imagem (carregado sob demanda).
import Plotly from 'plotly.js/dist/plotly'
import createPlotlyComponent from 'react-plotly.js/factory'

export const Plot = createPlotlyComponent(Plotly)
export const resize = (graph: HTMLElement) => Plotly.Plots.resize(graph)
export const downloadImage = (graph: HTMLElement, options: { filename: string; scale?: number }) =>
  Plotly.downloadImage(graph, { format: 'png', ...options })
