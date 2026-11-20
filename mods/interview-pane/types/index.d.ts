export type InterviewOption = { key: string; text: string }

export type InterviewStatus = 'open' | 'answered' | 'skipped'

export type InterviewQuestion = {
  id: string
  title: string
  body?: string
  options?: InterviewOption[]
  // An option key; the pane marks that option.
  recommended?: string
  recommendation?: string
  status: InterviewStatus
  answer?: string
}

export type InterviewState = {
  topic?: string
  questions: InterviewQuestion[]
  isFinished: boolean
  summary?: string
}

// One question's answer as sent, or a choice not yet sent. Kept apart from the
// questions so nothing changes status until the round is sent.
// `none` records that the person unpicked the recommended option; `other`
// that they chose the Other box, whose text is read from `drafts` on send.
export type InterviewStaged =
  | { kind: 'option'; key: string }
  // `isRecommended`: the box still held the prefilled recommendation.
  | { kind: 'text'; text: string; isRecommended?: true }
  | { kind: 'other' }
  | { kind: 'none' }
  | { kind: 'skip' }
  | { kind: 'reopen' }

declare module 'claude-code' {
  interface PluginState {
    'interview-pane': {
      interview: Shaped<InterviewState>
      // Option picks and reopens; text answers are read from `drafts` on send.
      staged: Shaped<Record<string, InterviewStaged>>
      // Text typed in each question's box; absent means the box still holds
      // the recommendation.
      drafts: Shaped<Record<string, string>>
      // Text in each question's Discuss box, sent in place of its answer.
      discussions: Shaped<Record<string, string>>
    }
  }
}
