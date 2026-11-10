declare module 'plotly.js/dist/plotly' {
  const Plotly: { downloadImage: (graph: HTMLElement, options: Record<string, unknown>) => Promise<string>; Plots: { resize: (graph: HTMLElement) => void } } & Record<string, unknown>
  export default Plotly
}
