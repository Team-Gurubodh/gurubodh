# Discovery Interviews

Use this shared procedure when discovering or revising requirements or design.
The [slice workflow](slice-workflow.md#requirements-and-approval) owns required
outcomes and approval rules. [slice-session](../../.agents/skills/slice-session/SKILL.md)
covers requirements; [slice-design-review](../../.agents/skills/slice-design-review/SKILL.md)
covers design. Routine restoration of accepted work does not restart discovery.

## Establish What Is Known

Read relevant issue records and inspect the implementation before asking questions.
Distinguish inspected facts (with evidence), explicit maintainer decisions (with
their source), agent recommendations (with rationale), and unresolved assumptions.
Reuse established answers. Reopen an accepted decision only when new evidence
warrants reconsideration, and explain that evidence.

## Ask and Follow Through

- Normally ask one question at a time. Group two or three independent questions
  when the interface makes separate answers clear. No particular question tool
  is required, and there is no fixed total question count.
- Offer choices when there is a real decision, explain consequences, recommend
  a researched option, and allow a free-form answer. Use an open question when
  suggested choices would restrict discovery. Resolve routine technical details
  using repository conventions and the accepted design.
- Follow dependencies. For example, “retry failed imports” leaves open whether
  completed writes survive, how duplicate writes are prevented, and what counts
  appear in the result. Settle those consequences before synthesizing guarantees.
- Test understanding with concrete success, failure, and boundary examples.
  Surface contradictory answers by stating the conflict and the affected work;
  do not silently choose one interpretation.
- Distinguish required answers from optional preferences using the workflow's
  [question classifications](slice-workflow.md#discovery-questions). Name
  affected dependencies and the resolution point. For a nonblocking preference,
  explain why current work is independent and state any proposed default as an
  agent recommendation, not a maintainer decision.

## Synthesize and Resume

Conclude when the behavior/design can be stated, verified, and approved and all
remaining questions have a classification, affected scope, and resolution point.
Brevity alone is not a stopping condition. Present one complete identified
synthesis for acceptance; during discussion, show affected changes instead of
repeating the full proposal after each answer.

Write requirements and decisions with a clear actor, trigger, behavior, and
observable result where those elements apply. Define terms that could change
scope, and expose unresolved ambiguity. Use the [record formats](templates/slice-records.md)
to retain decisions, rationale, examples, acceptance scope, and open questions
without routinely copying the interview transcript.

If design reveals a product gap, return only affected requirements and dependent
design decisions to review under the workflow's revision rules. If discussion
pauses, preserve the synthesis's actual status and unanswered questions. On
resumption, reuse answers and valid acceptance; distinguish a recorded decision
from accepted-but-unsaved discussion or unverified publication.

## Conductor Adaptation

This procedure uses original Gurubodh wording informed by Google Gemini
Conductor's [new-track](https://github.com/gemini-cli-extensions/conductor/blob/6e8f9a860bcdd6a2c423473c12e745200688c633/skills/conductor-new-track/SKILL.md)
and [setup](https://github.com/gemini-cli-extensions/conductor/blob/6e8f9a860bcdd6a2c423473c12e745200688c633/skills/conductor-setup/SKILL.md)
skills at revision `6e8f9a860bcdd6a2c423473c12e745200688c633`. The reviewed
upstream source is Apache-2.0 licensed; no upstream text is vendored here. See
the [accepted adaptation](https://github.com/Team-Gurubodh/gurubodh/issues/365#issuecomment-5825656990).

Adopt context-informed questions, suggested alternatives with custom answers,
follow-up rounds, summaries, and distinct specification/plan approval to resolve
decisions before implementation. Adapt inspection and resumption from setup to
avoid repeated discovery; use requirement-based decomposition and verification
checkpoints within existing slice coverage and phases.

Do not adopt fixed question counts, mandatory multiple-choice questions,
repeated readiness confirmations, inferred product decisions, a separate setup
mode, track files/registry, plugin installation, or Git-note, automatic commit,
deployment, and revert behavior. Repository lifecycle and GitHub authority remain
unchanged.
