import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { InterviewQuestion, InterviewState } from '../types'
import {
  type AnswerSource,
  type QuestionInput,
  answerOf,
  boxText,
  collectAnswers,
  emptyInterview,
  formatSend,
  mergeQuestions,
  pickedKey,
  settleRound,
  stageAnswer,
  unstageAnswer,
} from './model'

const PANE = 'interview'
const TOOL = 'mcp__interview-pane__interview'

// Change a tag when the shape of its value changes: state outlives a reload,
// and a value stored under another tag is read as the initial.
const interview = atom(
  { plugin: 'interview-pane', key: 'interview' } as const,
  emptyInterview,
  { shape: 'interview-1' },
)
const staged = atom(
  { plugin: 'interview-pane', key: 'staged' } as const,
  {},
  // staged-2: text answers are no longer staged, they are read from the box.
  { shape: 'staged-2' },
)
const drafts = atom(
  { plugin: 'interview-pane', key: 'drafts' } as const,
  {},
  // drafts-2: an empty string now means the person cleared the box, so older
  // values (emptied by staging) are dropped to let the recommendation show.
  { shape: 'drafts-2' },
)
// What each question's Discuss box holds: sent with the round as a question
// for Claude, in place of that question's answer.
const discussions = atom(
  { plugin: 'interview-pane', key: 'discussions' } as const,
  {},
  { shape: 'discussions-1' },
)

type ToolInput = {
  topic?: string
  questions?: QuestionInput[]
  finished?: boolean
  summary?: string
  reset?: boolean
}

const TOOL_DESCRIPTION = [
  'Interview the user in a pane beside the chat instead of in chat.',
  'Use it when you need decisions or facts from the user: ask one to three questions per round, each with a recommendation (give options with a recommended key where the answer is a choice).',
  'The call returns at once and does not wait: after it, end your turn. The user picks or writes answers in the pane, then submits the round; the answers arrive as the next user message.',
  'That message may also list questions under "Discuss (not answered yet)": answer those in chat, leave them open, and update their recommendation through this tool if it changes.',
  'Questions are merged by id, so to change one, send its id with only the changed fields. Earlier questions stay visible.',
  'When the user asks to finish, call it again with finished: true and a summary. reset: true starts a new interview.',
].join(' ')

const TOOL_SCHEMA = {
  type: 'object',
  properties: {
    topic: { type: 'string', description: "The interview's title." },
    questions: {
      type: 'array',
      description:
        'Questions to show, merged into the interview by id: a new id is appended, an existing id keeps any field this call omits.',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string', description: 'Stable id such as q1.' },
          title: {
            type: 'string',
            description: 'The question. Required for a new id.',
          },
          body: { type: 'string', description: 'Context, markdown allowed.' },
          options: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                key: { type: 'string', description: 'Short label such as A.' },
                text: { type: 'string' },
              },
              required: ['key', 'text'],
            },
          },
          recommended: {
            type: 'string',
            description: 'The key of the option you recommend.',
          },
          recommendation: {
            type: 'string',
            description: 'Why you recommend it, or your suggested answer.',
          },
          status: { type: 'string', enum: ['open', 'answered', 'skipped'] },
          answer: { type: 'string' },
        },
        required: ['id'],
      },
    },
    finished: {
      type: 'boolean',
      description: 'Mark the interview finished and show the summary.',
    },
    summary: {
      type: 'string',
      description: 'Closing summary, markdown allowed.',
    },
    reset: {
      type: 'boolean',
      description: 'Start a new interview, clearing earlier questions.',
    },
  },
} as const

type Engine = EngineInterface

// Every question answers as it stands (see answerOf), so one press sends the
// round: what is sent is read from the picks and the boxes at that moment.
// A question with discussion sends that instead and stays open.
async function sendRound($: Engine) {
  const state = await read($, interview)
  const talk = await read($, discussions)
  const answers = collectAnswers(state, await read($, staged), await read($, drafts), talk)
  const text = formatSend(state, answers, talk)
  if (text === '') return

  await update($, interview, current => settleRound(current, answers))
  await update($, staged, current => {
    // A discussed question keeps its pick for the next round.
    const kept: typeof current = {}
    for (const [id, choice] of Object.entries(current)) {
      if (answers[id] === undefined && choice.kind !== 'reopen') kept[id] = choice
    }
    return kept
  })
  await update($, discussions, () => ({}))
  await $.prompt.submit({ text, asUser: true })
}

const writeDiscussion = ($: Engine, id: string, text: string) =>
  update($, discussions, current => ({ ...current, [id]: text }))

// A key in `discussions` is what shows a card's Discuss box, so pressing
// Discuss adds an empty one and pressing it again removes it, text and all.
const toggleDiscussion = ($: Engine, id: string) =>
  update($, discussions, current => {
    if (current[id] === undefined) return { ...current, [id]: '' }
    const { [id]: _closed, ...rest } = current
    return rest
  })

// Grill-me's own wording: the recommended option, then why.
function recommendationLine(question: InterviewQuestion): string | undefined {
  const why = question.recommendation?.trim() ?? ''
  const key = question.recommended
  if (key !== undefined && why !== '') return `Recommendation: ${key}, because ${why}`
  if (key !== undefined) return `Recommendation: ${key}`
  if (why !== '') return `Recommendation: ${why}`
  return undefined
}

const stage = ($: Engine, id: string, choice: Parameters<typeof stageAnswer>[2]) =>
  update($, staged, current => stageAnswer(current, id, choice))

const unstage = ($: Engine, id: string) =>
  update($, staged, current => unstageAnswer(current, id))

// Pressing the picked option unpicks it, even when it was picked only by
// being the recommendation.
async function pressOption($: Engine, question: InterviewQuestion, key: string) {
  const choice = (await read($, staged))[question.id]
  if (pickedKey(question, choice) === key) {
    await stage($, question.id, { kind: 'none' })
  } else {
    await stage($, question.id, { kind: 'option', key })
  }
}

// Typing in an option question's Other box chooses Other, as it does in
// Claude's question dialog; emptying it hands the answer back to the options.
async function typeInto($: Engine, question: InterviewQuestion, text: string) {
  await update($, drafts, current => ({ ...current, [question.id]: text }))
  if (question.options === undefined) return
  const choice = (await read($, staged))[question.id]
  if (text.trim() !== '') {
    if (choice?.kind !== 'other') await stage($, question.id, { kind: 'other' })
  } else if (choice?.kind === 'other') {
    await unstage($, question.id)
  }
}

type CardState = AnswerSource | 'discussing' | 'answered' | 'skipped' | 'reopening'

// Colour marks progress only: blue is "will be sent", whoever chose the
// answer (the tag says which), green is sent, and grey is left for a question
// that will be skipped. Nothing reads as a warning or an error.
const LOOK: Record<CardState, { border?: string; color: string; label: string }> = {
  yours: { border: 'suggestion', color: 'suggestion', label: 'Your answer' },
  recommended: { border: 'suggestion', color: 'suggestion', label: 'Recommended answer' },
  none: { color: 'inactive', label: 'No answer, will be skipped' },
  discussing: { border: 'suggestion', color: 'suggestion', label: 'Question for Claude' },
  reopening: { border: 'suggestion', color: 'suggestion', label: 'Reopening' },
  answered: { border: 'success', color: 'success', label: 'Answered' },
  skipped: { color: 'inactive', label: 'Skipped' },
}

function cardState(
  question: InterviewQuestion,
  source: AnswerSource,
  isDiscussing: boolean,
): CardState {
  if (question.status === 'open') return isDiscussing ? 'discussing' : source
  if (source === 'yours') return 'reopening'
  return question.status
}

function resultText(isPlaced: boolean, state: InterviewState) {
  if (state.isFinished) {
    return 'The interview is marked finished and the summary is shown in the pane.'
  }
  if (!isPlaced) {
    return 'The interview pane is not placed (no room or no surface for it). Ask the same questions in chat instead, and take the answers from the next user message.'
  }
  const open = state.questions.filter(one => one.status === 'open').length
  return `The questions are shown in the interview pane (${open} open of ${state.questions.length}). End your turn now: do not wait or call this tool again. The user will answer in the pane and submit the round, and their answers will arrive as the next user message.`
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'interview',
      description: 'Open the interview pane',
    })
    await $.tool.register({
      name: 'interview',
      description: TOOL_DESCRIPTION,
      inputSchema: TOOL_SCHEMA,
      isDeferred: false,
    })

    return next(e)
  })

  on('command.run', { command: 'interview' }, async $ => {
    const opened = await $.ui.open({ id: PANE, title: 'Interview' })

    return {
      text: opened.isPlaced
        ? 'Interview pane opened.'
        : 'The interview pane is not placed: the terminal is too narrow or no surface is attached.',
    }
  })

  on('tool.call', { tool: TOOL }, async ($, e) => {
    const input = e as unknown as ToolInput

    if (input.reset === true) {
      await update($, interview, () => emptyInterview)
      await update($, staged, () => ({}))
      await update($, drafts, () => ({}))
      await update($, discussions, () => ({}))
    }

    const incoming = input.questions ?? []
    await update($, interview, current => ({
      ...current,
      topic: input.topic ?? current.topic,
      questions: mergeQuestions(current.questions, incoming),
      isFinished: input.finished ?? current.isFinished,
      summary: input.summary ?? current.summary,
    }))

    // A question the model has just set a status on is no longer waiting on
    // whatever was staged for it.
    const settled = incoming.filter(one => one.status !== undefined)
    if (settled.length > 0) {
      await update($, staged, current => {
        let next = current
        for (const one of settled) next = unstageAnswer(next, one.id)
        return next
      })
    }

    const opened = await $.ui.open({ id: PANE, title: 'Interview' })
    const state = await read($, interview)

    return { result: resultText(opened.isPlaced, state) }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button, Input, Markdown } = $.ui.resolve(e)
    const state = await read($, interview)
    const choices = await read($, staged)
    const typed = await read($, drafts)
    const talk = await read($, discussions)
    const isLive = !state.isFinished
    const total = state.questions.length
    const answered = state.questions.filter(one => one.status === 'answered').length
    const sources = new Map(
      state.questions.map(one => [one.id, answerOf(one, choices[one.id], typed)]),
    )
    const discussing = (question: InterviewQuestion) =>
      question.status === 'open' && (talk[question.id] ?? '').trim() !== ''
    const askCount = state.questions.filter(discussing).length
    const count = state.questions.filter(
      one => !discussing(one) && sources.get(one.id)?.answer !== undefined,
    ).length
    const sendLabel = [
      count > 0 ? `${count} answer${count === 1 ? '' : 's'}` : undefined,
      askCount > 0 ? `${askCount} question${askCount === 1 ? '' : 's'}` : undefined,
    ]
      .filter(Boolean)
      .join(' and ')

    const Tag = ({ look }: { look: CardState }) => (
      <Text size="footnote" weight="semibold" color={LOOK[look].color}>
        {LOOK[look].label}
      </Text>
    )

    return (
      <Box flexDirection="column" gap="md">
        <Box flexDirection="column">
          <Text size="heading" weight="semibold">
            {state.topic ?? 'Interview'}
          </Text>
          <Text size="footnote" dimColor>
            {total === 0
              ? 'No questions yet.'
              : `${answered} of ${total} answered`}
          </Text>
        </Box>

        {state.isFinished && (
          <Box
            flexDirection="column"
            gap="sm"
            borderStyle="round"
            borderColor="success"
            padding="md"
          >
            <Text weight="semibold" color="success">
              Finished
            </Text>
            {state.summary !== undefined && <Markdown text={state.summary} />}
          </Box>
        )}

        {state.questions.map((question, index) => {
          // The id is the model's handle; the person reads the position.
          const title = `${index + 1}. ${question.title}`
          const choice = choices[question.id]
          const isDiscussing = discussing(question)
          const look = cardState(
            question,
            sources.get(question.id)?.source ?? 'none',
            isDiscussing,
          )

          // A settled question collapses to its title and answer, so the open
          // ones stay near the top as rounds pile up.
          if (question.status !== 'open') {
            const isReopening = look === 'reopening'
            return (
              <Box
                key={`q:${question.id}`}
                flexDirection="column"
                gap="xs"
                borderStyle="round"
                borderColor={LOOK[look].border}
                borderDimColor={LOOK[look].border === undefined}
                paddingX="md"
                paddingY="sm"
              >
                <Box
                  flexDirection="row"
                  gap="sm"
                  alignItems="center"
                  justifyContent="space-between"
                >
                  <Box flexShrink={1}>
                    <Text weight="medium" dimColor wrap="truncate-end">
                      {title}
                    </Text>
                  </Box>
                  <Tag look={look} />
                </Box>
                <Text wrap="wrap" dimColor={question.status === 'skipped'}>
                  {question.status === 'skipped'
                    ? 'Skipped'
                    : `Answer: ${question.answer ?? ''}`}
                </Text>
                {isLive && (
                  <Box flexDirection="row">
                    <Button
                      key={`reopen:${question.id}`}
                      label={isReopening ? 'Keep answer' : 'Reopen'}
                      dimColor
                      onPress={() =>
                        isReopening
                          ? unstage($, question.id)
                          : stage($, question.id, { kind: 'reopen' })
                      }
                    />
                  </Box>
                )}
              </Box>
            )
          }

          const picked = pickedKey(question, choice)

          return (
            <Box
              key={`q:${question.id}`}
              flexDirection="column"
              gap="sm"
              borderStyle="round"
              borderColor={LOOK[look].border}
              borderDimColor={LOOK[look].border === undefined}
              padding="md"
            >
              <Box
                flexDirection="row"
                gap="sm"
                alignItems="flex-start"
                justifyContent="space-between"
              >
                <Box flexShrink={1}>
                  <Text weight="semibold" wrap="wrap">
                    {title}
                  </Text>
                </Box>
                {isLive && <Tag look={look} />}
              </Box>
              {question.body !== undefined && <Markdown text={question.body} />}

              {isLive && question.options !== undefined && (
                <Box flexDirection="column" gap="xs">
                  {question.options.map(option => {
                    const isPicked = picked === option.key
                    // Once one is picked the rest step back, so the choice
                    // reads at a glance; each stays pressable to change it.
                    const isFaded = picked !== undefined && !isPicked

                    return (
                      <Box
                        key={`row:${question.id}:${option.key}`}
                        flexDirection="row"
                        gap="sm"
                        alignItems="center"
                      >
                        <Button
                          key={`opt:${question.id}:${option.key}`}
                          label={option.key}
                          variant={isPicked ? 'primary' : 'secondary'}
                          dimColor={isFaded}
                          onPress={() => pressOption($, question, option.key)}
                        />
                        <Box flexShrink={1}>
                          <Text
                            wrap="wrap"
                            weight={isPicked ? 'semibold' : undefined}
                            dimColor={isFaded}
                          >
                            {option.text}
                            {question.recommended === option.key && (
                              <Text size="footnote" dimColor>
                                {'   (recommended)'}
                              </Text>
                            )}
                          </Text>
                        </Box>
                      </Box>
                    )
                  })}
                </Box>
              )}

              {isLive && (
                // On an option question the box is one more choice, Other, as
                // Claude's question dialog has it; typing in it chooses it.
                <Box flexDirection="row" gap="sm" alignItems="center">
                  {question.options !== undefined && (
                    <Text
                      weight={choice?.kind === 'other' ? 'semibold' : undefined}
                      dimColor={picked !== undefined}
                    >
                      Other:
                    </Text>
                  )}
                  {/* A one-row field is drawn at its own width unless its box
                      claims the room, so the box takes the rest of the row. */}
                  <Box flexDirection="column" flexGrow={1}>
                    <Input
                      key={`text:${question.id}`}
                      placeholder={
                        question.options === undefined
                          ? 'Your answer'
                          : 'Your own answer'
                      }
                      // One row: the desktop draws a submit button beside a
                      // multi-row field and none beside a one-row field.
                      // Enter only keeps the text; Send at the bottom sends.
                      value={boxText(question, typed)}
                      onInput={value => void typeInto($, question, value)}
                      onSubmit={value => void typeInto($, question, value)}
                    />
                  </Box>
                </Box>
              )}

              {/* The recommendation and its reasoning, as grill-me gives it in
                  chat; kept in view even after the box is edited. */}
              {isLive && recommendationLine(question) !== undefined && (
                <Text size="footnote" dimColor wrap="wrap">
                  {recommendationLine(question)}
                </Text>
              )}

              {/* Discussion goes out with the round and leaves the question
                  unanswered, so its answer is not sent this time. The box
                  shows only on the cards where Discuss was pressed. */}
              {isLive && talk[question.id] !== undefined && (
                <Box flexDirection="row" gap="sm" alignItems="center">
                  <Text dimColor={!isDiscussing}>Discuss:</Text>
                  <Box flexDirection="column" flexGrow={1}>
                    <Input
                      key={`discuss:${question.id}`}
                      placeholder="Ask about the reasoning or a trade-off"
                      autoFocus
                      value={talk[question.id] ?? ''}
                      onInput={value => void writeDiscussion($, question.id, value)}
                      onSubmit={value => void writeDiscussion($, question.id, value)}
                    />
                  </Box>
                </Box>
              )}

              {isLive && (
                <Box flexDirection="row">
                  <Button
                    key={`discuss-toggle:${question.id}`}
                    label={talk[question.id] === undefined ? 'Discuss' : 'Cancel discussion'}
                    dimColor
                    onPress={() => toggleDiscussion($, question.id)}
                  />
                </Box>
              )}
            </Box>
          )
        })}

        {isLive && total > 0 && (
          <Box flexDirection="row" gap="sm" alignItems="center">
            {sendLabel !== '' ? (
              <Button
                key="submit"
                label={`Send ${sendLabel}`}
                variant="primary"
                onPress={() => sendRound($)}
              />
            ) : (
              <Text size="footnote" dimColor>
                Pick or write an answer to send it.
              </Text>
            )}
          </Box>
        )}
      </Box>
    )
  })
}
