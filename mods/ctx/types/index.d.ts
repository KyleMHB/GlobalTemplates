export type ContextReading = { tokens: number; window: number }

declare module 'claude-code' {
  interface PluginState {
    'ctx': { reading: ContextReading | null }
  }
}
