# Plan Operation

Turn review evidence into a user-approved, decision-complete implementation plan. This operation may write only the final dated plan artifact. It must not implement mod changes, rewrite the source review, change Git state, publish, or perform other external mutations.

## Select and verify the review

1. When the user names a review file, use that file.
2. Otherwise, find files in the mod root named `review YYYY-MM-DD.md` and use the newest valid date.
3. If no dated review exists, explain that planning requires one and ask whether to run review mode. Wait for approval before starting the review.
4. Establish whether relevant mod files changed after the selected review. Use Git history and status when available, plus file timestamps or other repository evidence when needed.
5. Inspect changed areas that could affect selected findings. Correct stale conclusions in the planning conversation and final plan, and identify which original finding has been superseded. Do not edit the historical review. A complete new audit is unnecessary unless the changes invalidate the review broadly; ask before switching to review mode.

## Establish intent

Plans cover only the findings and outcomes the user selects. Do not automatically convert the entire roadmap or the review's first batch into the plan.

Ground the conversation in the review and current repository before asking questions. Resolve discoverable facts by inspecting source, configuration, documentation, history, build tooling, and applicable repository instructions. Ask focused questions only when the answer changes scope, behavior, architecture, compatibility, risk, delivery, or user-visible results.

Continue the planning conversation until all material decisions are resolved. Cover the applicable choices among:

- selected finding IDs, desired outcomes, priorities, and acceptance criteria;
- explicit exclusions and behavior that must remain unchanged;
- supported game, framework, dependency, save, and multiplayer compatibility;
- implementation approach, public interfaces, data flow, migrations, failure handling, and recovery;
- performance constraints and how suspected hot paths will be measured;
- validation, packaging, documentation, versioning, release handling, and sequencing.

Ask in small, coherent groups. Offer a recommended default and its tradeoff when useful. Do not ask the user to decide facts that the repository can answer, and do not use repeated confirmation questions as a substitute for analysis.

## Approval gate

Before writing any plan file, summarize the understood goals, selected findings, scope, exclusions, constraints, key implementation decisions, validation expectations, and delivery boundaries. Ask the user to explicitly confirm or correct that understanding.

If feedback changes a material decision, inspect any newly relevant evidence, update the summary, and request confirmation again. Approval applies only to the summarized plan scope. Do not treat silence, partial answers, or approval of an earlier materially different summary as final approval.

## Write the plan

After explicit approval, write the complete plan to `plan YYYY-MM-DD.md` in the mod root using the current local date. If that day's plan already exists, replace it only after the approved replacement is complete. Do not create numbered same-day variants.

Make the plan ready for another engineer or agent to implement without choosing missing behavior. Include, when applicable:

1. A clear title and concise outcome summary.
2. The source review filename, selected finding IDs, and any findings corrected after checking later changes.
3. Implementation changes grouped by behavior or subsystem.
4. Public API, schema, configuration, persistence, and compatibility changes.
5. Error handling, edge cases, migration, rollback, and safe failure behavior.
6. Tests and acceptance scenarios with observable expected results.
7. Packaging, documentation, versioning, rollout, and validation requirements.
8. Explicit assumptions and user-approved defaults.

Keep the plan proportional to the selected work. Preserve stable finding IDs so the plan remains traceable to its review. Clearly distinguish confirmed work from optional follow-ups.

Return a concise summary and a link to the saved plan. State that implementation has not started and requires separate authorization.
