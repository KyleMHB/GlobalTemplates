import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { ContextReading } from '../types'

const PANE = 'context-usage'
const RED_AT = 300_000
const ORANGE_AT = 150_000

const reading = atom(
  { plugin: 'ctx', key: 'reading' } as const,
  null as ContextReading | null,
)

const formatTokens = (n: number): string =>
  n >= 1_000_000
    ? `${+(n / 1_000_000).toFixed(1)}M`
    : n >= 1_000
      ? `${(n / 1_000).toFixed(1)}K`
      : `${n}`

const colorFor = (tokens: number): string =>
  tokens >= RED_AT ? '#e5484d' : tokens >= ORANGE_AT ? '#f5a524' : '#46a758'

const toReading = (tokens: number | undefined, window: number): ContextReading | null =>
  tokens === undefined ? null : { tokens, window }

// The status line is plain text, so the colour rides on the dot.
const dotFor = (tokens: number): string =>
  tokens >= RED_AT ? '🔴' : tokens >= ORANGE_AT ? '🟠' : '🟢'

const show = async ($: EngineInterface, r: ContextReading | null) => {
  $.ui.status(r === null ? undefined : `${dotFor(r.tokens)} ${formatTokens(r.tokens)} / ${formatTokens(r.window)}`)
  // The atom keeps the breakdown pane redrawing after each turn.
  await update($, reading, () => r)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const result = await next(e)
    await $.command.register({
      name: 'context-usage',
      description: 'Show how the context window is being used, by category',
    })
    const { context } = await $.session.usage()
    await show($, toReading(context.tokens, context.window))
    return result
  })

  on('session.measure', async ($, e, next) => {
    await show($, toReading(e.context.tokens, e.context.window))
    return next(e)
  })

  // The status line can't be clicked, so the breakdown pane opens from a command.
  on('command.run', { command: 'context-usage' }, async $ => {
    await $.ui.open({ id: PANE, title: 'Context usage', focus: true, closeOnEscape: true })
    return { text: 'Context usage pane opened.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Progress } = $.ui.resolve(e)
    // Reading the atom redraws the pane after every turn.
    const r = await read($, reading)
    const { context } = await $.session.usage({ breakdown: 'summary' })
    const b = context.breakdown

    if (r === null || b === undefined) {
      return <Text dimColor>No context reading yet: it appears after the first response.</Text>
    }

    const color = colorFor(r.tokens)
    const shown = b.categories.filter(c => c.kind !== 'deferred' && c.tokens > 0)
    const deferred = b.categories.filter(c => c.kind === 'deferred' && c.tokens > 0)
    const share = (n: number) => `${((n / b.rawMaxTokens) * 100).toFixed(1)}%`

    return (
      <Box flexDirection="column" gap={1}>
        <Box flexDirection="column">
          <Text bold color={color}>
            {formatTokens(r.tokens)} / {formatTokens(r.window)} used
          </Text>
          <Text dimColor>{b.model}</Text>
        </Box>
        <Progress
          label="Context used"
          value={r.tokens}
          max={r.window}
          valueText={`${formatTokens(r.tokens)} of ${formatTokens(r.window)}`}
          color={color}
        />
        <Box flexDirection="column">
          {shown.map(c => (
            <Box key={c.name} flexDirection="row" justifyContent="space-between">
              <Text>
                <Text color={c.color}>■ </Text>
                {c.name}
              </Text>
              <Text dimColor>
                {formatTokens(c.tokens)} · {share(c.tokens)}
              </Text>
            </Box>
          ))}
        </Box>
        {deferred.length > 0 && (
          <Box flexDirection="column">
            <Text dimColor>Loaded on demand, not counted</Text>
            {deferred.map(c => (
              <Box key={c.name} flexDirection="row" justifyContent="space-between">
                <Text dimColor>{c.name}</Text>
                <Text dimColor>{formatTokens(c.tokens)}</Text>
              </Box>
            ))}
          </Box>
        )}
        {b.isAutoCompactEnabled && b.autoCompactThreshold !== undefined && (
          <Text dimColor>Auto-compacts at {formatTokens(b.autoCompactThreshold)}</Text>
        )}
      </Box>
    )
  })
}
