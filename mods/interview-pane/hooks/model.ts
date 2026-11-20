import type {
  InterviewQuestion,
  InterviewStaged,
  InterviewState,
} from '../types'

export type QuestionInput = Partial<Omit<InterviewQuestion, 'id'>> & {
  id: string
}

export type StagedMap = Record<string, InterviewStaged>

export const emptyInterview: InterviewState = {
  questions: [],
  isFinished: false,
}

// --- Questions arriving from the tool -------------------------------------

// The model may call the tool again with only what changed, so a field the
// call leaves out keeps its old value.
export function mergeQuestions(
  list: InterviewQuestion[],
  incoming: QuestionInput[],
): InterviewQuestion[] {
  const merged = [...list]
  for (const input of incoming) {
    const fields = Object.fromEntries(
      Object.entries(input).filter(([, value]) => value !== undefined),
    )
    const index = merged.findIndex(question => question.id === input.id)
    const existing = merged[index]
    if (existing === undefined) {
      merged.push({
        title: input.id,
        status: 'open',
        ...fields,
      } as InterviewQuestion)
    } else {
      merged[index] = { ...existing, ...fields }
    }
  }
  return merged
}

// --- Staging: what the person has chosen, nothing sent yet ----------------

export function optionLabel(question: InterviewQuestion, key: string): string {
  const option = question.options?.find(one => one.key === key)
  return option === undefined ? key : `${option.key} — ${option.text}`
}

export function stageAnswer(
  staged: StagedMap,
  id: string,
  choice: InterviewStaged,
): StagedMap {
  return { ...staged, [id]: choice }
}

export function unstageAnswer(staged: StagedMap, id: string): StagedMap {
  const { [id]: _removed, ...rest } = staged
  return rest
}

// --- Answers: what a question will send, read from the pane as it stands ---

// Where an open question's answer comes from, which the card shows: the
// person's own pick or text, the recommendation left in place, or nothing.
export type AnswerSource = 'yours' | 'recommended' | 'none'

export type Drafts = Record<string, string>

function recommendedKey(question: InterviewQuestion): string | undefined {
  const key = question.recommended
  return key !== undefined && question.options?.some(one => one.key === key)
    ? key
    : undefined
}

// On an option question the box is the Other option, as in Claude's own
// question dialog, and starts empty. On a free-text question it is the
// answer, and starts with the recommendation.
export function boxText(question: InterviewQuestion, drafts: Drafts): string {
  return (
    drafts[question.id] ??
    (question.options === undefined ? (question.recommendation ?? '') : '')
  )
}

// The option an open question has picked: the person's pick, else the
// recommended one, unless the person unpicked it or chose Other.
export function pickedKey(
  question: InterviewQuestion,
  choice: InterviewStaged | undefined,
): string | undefined {
  if (choice?.kind === 'option') return choice.key
  if (choice === undefined) return recommendedKey(question)
  return undefined
}

// Every question answers as it stands, so sending needs no per-question step:
// the picked option, or the Other box when it is chosen, or a free-text
// question's box. Empty is skipped.
export function answerOf(
  question: InterviewQuestion,
  choice: InterviewStaged | undefined,
  drafts: Drafts,
): { answer?: InterviewStaged; source: AnswerSource } {
  if (question.status !== 'open') {
    return choice?.kind === 'reopen'
      ? { answer: choice, source: 'yours' }
      : { source: 'none' }
  }
  const text = boxText(question, drafts).trim()

  if (question.options === undefined) {
    if (text === '') return { source: 'none' }
    return text === (question.recommendation ?? '').trim()
      ? { answer: { kind: 'text', text, isRecommended: true }, source: 'recommended' }
      : { answer: { kind: 'text', text }, source: 'yours' }
  }

  if (choice?.kind === 'other') {
    return text === ''
      ? { source: 'none' }
      : { answer: { kind: 'text', text }, source: 'yours' }
  }
  const key = pickedKey(question, choice)
  if (key === undefined) return { source: 'none' }
  return {
    answer: { kind: 'option', key },
    source: choice?.kind === 'option' ? 'yours' : 'recommended',
  }
}
// A question with discussion sends no answer: discussing it leaves it open,
// as grill-me keeps an answer apart from a request to discuss it.
export function collectAnswers(
  interview: InterviewState,
  staged: StagedMap,
  drafts: Drafts,
  discussions: Drafts = {},
): StagedMap {
  const answers: StagedMap = {}
  for (const question of interview.questions) {
    if (question.status === 'open' && (discussions[question.id] ?? '').trim() !== '') continue
    const { answer } = answerOf(question, staged[question.id], drafts)
    if (answer !== undefined) answers[question.id] = answer
  }
  return answers
}

export function describeStaged(
  question: InterviewQuestion,
  choice: InterviewStaged,
): string {
  switch (choice.kind) {
    case 'option':
      return optionLabel(question, choice.key)
    case 'text':
      // A kept recommendation is not the person's own wording.
      return `${choice.isRecommended ? '(recommended)' : '(own answer)'} ${choice.text}`
    case 'other':
      return 'other'
    case 'none':
      return 'no answer'
    case 'skip':
      return 'skipped'
    case 'reopen':
      return 'reopened'
  }
}

// --- Sending: turning staged choices into one message and new statuses -----

export function stagedCount(interview: InterviewState, staged: StagedMap) {
  return interview.questions.filter(question => staged[question.id]).length
}

// Follows the question order, so the message reads like the pane.
export function formatRound(
  interview: InterviewState,
  staged: StagedMap,
): string {
  const lines: string[] = []
  for (const question of interview.questions) {
    const choice = staged[question.id]
    if (choice !== undefined) {
      lines.push(
        `- ${question.id} "${question.title}": ${describeStaged(question, choice)}`,
      )
    }
  }
  return lines.length === 0 ? '' : ['Interview answers', ...lines].join('\n')
}

// The round as one message: the answers, then the questions to discuss,
// which are marked as not answered so they are kept apart.
export function formatSend(
  interview: InterviewState,
  answers: StagedMap,
  discussions: Drafts,
): string {
  const talk = interview.questions
    .filter(question => question.status === 'open')
    .map(question => [question, (discussions[question.id] ?? '').trim()] as const)
    .filter(([, text]) => text !== '')
    .map(([question, text]) => `- ${question.id} "${question.title}": ${text}`)
  const parts = [formatRound(interview, answers)]
  if (talk.length > 0) parts.push(['Discuss (not answered yet)', ...talk].join('\n'))
  return parts.filter(part => part !== '').join('\n\n')
}

// Applies what was sent, so the pane shows it without waiting for the model.
export function settleRound(
  interview: InterviewState,
  staged: StagedMap,
): InterviewState {
  const questions = interview.questions.map((question): InterviewQuestion => {
    const choice = staged[question.id]
    switch (choice?.kind) {
      case 'option':
        return {
          ...question,
          status: 'answered',
          answer: describeStaged(question, choice),
        }
      case 'text':
        return { ...question, status: 'answered', answer: choice.text }
      case 'skip':
        return { ...question, status: 'skipped', answer: undefined }
      case 'reopen':
        return { ...question, status: 'open', answer: undefined }
      default:
        return question
    }
  })
  return { ...interview, questions }
}
