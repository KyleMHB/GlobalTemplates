import { expect, test } from 'claude-code/testing'

const TOOL = 'mcp__interview-pane__interview'

const PANE = {
  plugin: 'interview-pane',
  component: 'Pane',
  requestId: 'interview',
  props: {
    title: 'Interview',
    isFocused: false,
    bodyColumns: 80,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 40 },
    view: {},
  },
} as const

// What the engine does beneath the plugin, answered from memory; every prompt
// the mod submits lands in `sent`.
async function start($: any, on: any, isPlaced = true) {
  const sent: string[] = []
  on('command.register', () => ({ value: { command: 'interview' } }))
  on('tool.register', () => ({ value: { tool: TOOL } }))
  on('ui.open', () => ({
    value: isPlaced ? { isPlaced: true } : { isPlaced: false, reason: 'narrow' },
  }))
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  on('prompt.submit', (_: unknown, e: { text: string }) => {
    sent.push(e.text)
    return { text: e.text }
  })
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  return sent
}

// The mod's state is read through what the pane draws: a test's `$` has no
// `state` noun of its own.
// A card's state is read from its tag.
const TAGS: [string, string][] = [
  ['Your answer', 'yours'],
  ['Recommended answer', 'recommended'],
  ['No answer', 'none'],
  ['Question for Claude', 'discussing'],
  ['Reopening', 'reopening'],
  ['Answered', 'answered'],
  ['Skipped', 'skipped'],
]

async function statusOf(ui: any, id: string): Promise<string | undefined> {
  const card = (await ui.find({ key: `q:${id}` }))?.text as string | undefined
  if (card === undefined) return undefined
  return TAGS.find(([tag]) => card.includes(tag))?.[1] ?? 'untagged'
}

// Titles are drawn with their position: `1. Who needs this?`.
async function hasTitle(ui: any, title: string): Promise<boolean> {
  return (await ui.find({ type: 'Text', text: new RegExp(`^\\d+\\. ${title.replace('?', '\\?')}$`) })) !== undefined
}

async function answerOf(ui: any): Promise<(string | undefined)[]> {
  return Promise.all(['q1', 'q2', 'q3', 'q4'].map(id => statusOf(ui, id)))
}

const ROUND_ONE = [
  {
    id: 'q1',
    title: 'Who needs this?',
    options: [
      { key: 'A', text: 'Individual users' },
      { key: 'B', text: 'Teams' },
    ],
    recommended: 'A',
    recommendation: 'Start narrow.',
  },
  { id: 'q2', title: 'Why now?' },
  { id: 'q3', title: 'Which platform?' },
  { id: 'q4', title: 'Old question', status: 'answered', answer: 'Z' },
]

test('the tool merges questions by id and returns at once', async ($, on) => {
  await start($, on)

  const first = await $.tool.call({
    tool: TOOL,
    topic: 'Scope',
    questions: ROUND_ONE.slice(0, 2),
  })
  expect(first.result).toContain('End your turn now')

  await $.tool.call({
    tool: TOOL,
    questions: [
      { id: 'q2', body: 'Context for q2' },
      { id: 'q5', title: 'A new one' },
    ],
  })

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  // The second call omitted the title and options, so those stay.
  // q1's recommended option answers it until the person picks otherwise.
  expect(await statusOf(ui, 'q1')).toBe('recommended')
  expect(await hasTitle(ui, 'Who needs this?')).toBe(true)
  expect(await statusOf(ui, 'q2')).toBe('none')
  expect(await hasTitle(ui, 'Why now?')).toBe(true)
  expect(await statusOf(ui, 'q5')).toBe('none')
  expect(await hasTitle(ui, 'A new one')).toBe(true)
  expect(await ui.find({ type: 'Markdown', text: /Context for q2/ })).toBeDefined()
  expect(await ui.find({ key: 'opt:q1:B' })).toBeDefined()
  expect((await ui.find({ type: 'Text', text: /^Scope$/ }))?.text).toBe('Scope')

  await $.tool.call({ tool: TOOL, reset: true, questions: [{ id: 'n1', title: 'Fresh' }] })
  expect(await statusOf(ui, 'n1')).toBe('none')
  expect(await hasTitle(ui, 'Fresh')).toBe(true)
  expect(await hasTitle(ui, 'Who needs this?')).toBe(false)
  expect(await statusOf(ui, 'q1')).toBeUndefined()
  await ui.unmount()
})

test('an unplaced pane tells the model to ask in chat', async ($, on) => {
  await start($, on, false)

  const ran = await $.tool.call({
    tool: TOOL,
    questions: [{ id: 'q1', title: 'Hello?' }],
  })

  expect(ran.result).toContain('Ask the same questions in chat')
})

test('every answer as it stands goes out in one message', async ($, on) => {
  const sent = await start($, on)
  await $.tool.call({ tool: TOOL, questions: ROUND_ONE })

  for (const surface of ['terminal', 'desktop'] as const) {
    sent.length = 0
    await $.tool.call({ tool: TOOL, reset: true, questions: ROUND_ONE })
    const ui = await $.ui.mount({ ...PANE, surface })

    // q1 keeps its recommended A with no press; q2 is typed; q3 is left
    // empty, which is how it is skipped.
    await ui.input({ key: 'text:q2', text: 'Because of the launch', kind: 'change' })
    await ui.press({ key: 'reopen:q4' })

    // Nothing is sent or settled until Send.
    expect(sent.length).toBe(0)
    expect(await statusOf(ui, 'q1')).toBe('recommended')
    expect(await statusOf(ui, 'q2')).toBe('yours')
    expect(await statusOf(ui, 'q3')).toBe('none')
    expect(await statusOf(ui, 'q4')).toBe('reopening')

    await ui.press({ key: 'submit' })

    expect(sent).toEqual([
      [
        'Interview answers',
        '- q1 "Who needs this?": A — Individual users',
        '- q2 "Why now?": (own answer) Because of the launch',
        '- q4 "Old question": reopened',
      ].join('\n'),
    ])

    expect(await answerOf(ui)).toEqual(['answered', 'answered', 'none', 'none'])
    expect(
      (await ui.find({ type: 'Text', text: /^Answer: A/ }))?.text,
    ).toBe('Answer: A — Individual users')
    expect(
      (await ui.find({ type: 'Text', text: /^Answer: Because/ }))?.text,
    ).toBe('Answer: Because of the launch')

    // Staging is cleared, and Reopen is offered on the answered ones.
    expect(await statusOf(ui, 'q1')).toBe('answered')
    expect(await ui.find({ key: 'reopen:q1' })).toBeDefined()
    await ui.unmount()
  }
})

test('discussion goes out with the round and leaves the question open', async ($, on) => {
  const sent = await start($, on)
  await $.tool.call({ tool: TOOL, questions: ROUND_ONE.slice(0, 2) })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })

  await ui.press({ key: 'opt:q1:B' })
  // The Discuss box shows only once Discuss is pressed on that card.
  expect(await ui.find({ key: 'discuss:q1' })).toBeUndefined()
  await ui.press({ key: 'discuss-toggle:q1' })
  await ui.input({ key: 'discuss:q1', text: 'What about freelancers?', kind: 'change' })
  await ui.input({ key: 'text:q2', text: 'Launch', kind: 'change' })
  expect(await statusOf(ui, 'q1')).toBe('discussing')

  await ui.press({ key: 'submit' })
  expect(sent).toEqual([
    [
      'Interview answers',
      '- q2 "Why now?": (own answer) Launch',
      '',
      'Discuss (not answered yet)',
      '- q1 "Who needs this?": What about freelancers?',
    ].join('\n'),
  ])

  // q1 stays open with its pick, which sends next round; its box closed.
  expect(await statusOf(ui, 'q1')).toBe('yours')
  expect(await ui.find({ key: 'discuss:q1' })).toBeUndefined()
  await ui.press({ key: 'submit' })
  expect(sent[1]).toBe('Interview answers\n- q1 "Who needs this?": B — Teams')
  await ui.unmount()
})

test('pressing the picked option unpicks it, recommended or not', async ($, on) => {
  const sent = await start($, on)
  await $.tool.call({ tool: TOOL, questions: ROUND_ONE.slice(0, 1) })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })

  await ui.press({ key: 'opt:q1:A' })
  expect(await statusOf(ui, 'q1')).toBe('none')
  expect(await ui.find({ key: 'submit' })).toBeUndefined()

  await ui.press({ key: 'opt:q1:B' })
  await ui.press({ key: 'submit' })
  expect(sent).toEqual(['Interview answers\n- q1 "Who needs this?": B — Teams'])
  await ui.unmount()
})

test('finished: true shows the summary and no input controls', async ($, on) => {
  await start($, on)
  await $.tool.call({ tool: TOOL, questions: ROUND_ONE.slice(0, 2) })
  await $.tool.call({
    tool: TOOL,
    finished: true,
    summary: 'We build for **individual users** first.',
  })

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })

    expect(await ui.find({ type: 'Text', text: /Finished/ })).toBeDefined()
    expect(
      (await ui.find({ type: 'Markdown', text: /individual users/ }))?.text,
    ).toContain('individual users')
    expect(await ui.find({ key: 'submit' })).toBeUndefined()
    expect(await ui.find({ key: 'finish' })).toBeUndefined()
    expect(await ui.find({ key: 'text:q1' })).toBeUndefined()
    expect(await ui.find({ key: 'opt:q1:A' })).toBeUndefined()
    await ui.unmount()
  }
})

test('a value an earlier version stored is declined', async ($, on) => {
  on('state.get', () => ({
    value: { value: { shape: 'old', value: [{ id: 'x' }] }, version: 1 },
  }))

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })

  expect((await ui.find({ type: 'Text', text: /No questions yet/ }))?.text).toBe(
    'No questions yet.',
  )
  await ui.unmount()
})
