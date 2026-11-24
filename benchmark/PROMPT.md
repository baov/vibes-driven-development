# The prompt

Every run receives this prompt verbatim, with `<FIXTURE>` replaced by the path
produced by `tools/setup_fixture.sh`. Nothing else is said to the agent.

```
You are contributing to the project located at <FIXTURE>

That project ships its own engineering harness. Before writing anything, read
`CLAUDE.md`, `AGENTS.md` and every skill under `.claude/skills/`. These project
instructions take precedence over your personal habits and over any other skill
collection you may have available — apply them strictly, including where they
contradict your usual reflexes. Do not import, invoke or follow any skill that
does not come from this project's `.claude/skills/` directory.

Task: add seat booking. A screening takes place in a room that has rows and
seats. A client can book a seat for a screening. Booking a seat that is already
booked must be rejected. The service must also expose the availability of every
seat of a screening.

Work only inside that directory. Python 3, standard library only. Run the tests
with `python3 -m unittest discover -s tests -t .` from the project root. Commit
your work following the Commits section of AGENTS.md.

When you are done, report: the files you created, and which specific rules from
AGENTS.md or from the skills shaped your implementation choices.
```

The prompt pushes toward compliance on purpose: it tells the agent the harness
outranks its own habits. A refusal recorded under that pressure is a strong
signal. Compliance under it is a weak one — the agent was told to comply.

Known bias: the closing question invites the agent to reason about the rules,
which may itself provoke refusals. The grid below is therefore scored from the
committed code, not from what the agent said about it.

## Variants (N run in batch 3, B in batch 4)

Variant N was run in batch 3 (see [`batch-3.md`](./batch-3.md)) and Task B in
batch 4 (see [`batch-4.md`](./batch-4.md)); no other result in the grid comes
from these. They exist so the next runs can test the biases
named above instead of only admitting them.

### Variant N — neutral prompt

Same task, but without the sentence that the harness outranks the agent's
habits, and without the closing report. The agent is only told to read the
project's instruction files and to commit following AGENTS.md. Comparing N with
the published prompt measures how much of the compliance was ordered.

```
You are contributing to the project located at <FIXTURE>. Read its
CLAUDE.md before starting.

Task: (same as above)

Work only inside that directory. Python 3, standard library only. Run the tests
with `python3 -m unittest discover -s tests -t .` from the project root. Commit
your work following the Commits section of AGENTS.md.
```

The commit sentence stays: without a commit there is nothing to score. It means
R10 is still prompted in this variant, so R10 is not a neutral measure here.

### Task B — a task that can actually trigger R3 and R5

Task A has a single failure path, so R3 (one long function) and R5 (log at
every layer) can go unapplied because they never came up. Task B has several:

```
Task: add seat booking with cancellation and refund. A screening has a start
time, a room with rows and seats, and a price. A client books a seat for a
screening; booking a seat that is already booked must be rejected. A client can
cancel a booking up to two hours before the screening starts. The refund goes
through a payment gateway passed to the service, which can fail transiently
(retry up to three times), fail permanently (the booking stays active), or be
unavailable (the cancellation is rejected). Cancelling an already cancelled or
unknown booking must be rejected. Expose the refund status of a booking.
```

Task B is self-contained (it builds the booking it cancels), because the fixture
is empty. It is given with the published prompt of Task A, only the task
paragraph differing. Scoring is unchanged. Report Task B grids separately: never
pool them with Task A.

### Environment isolation

Run each agent with an empty home directory so that no personal `CLAUDE.md`
leaks in, and record how it was done in the run notes:

```bash
HOME="$(mktemp -d)" ANTHROPIC_API_KEY=... claude -p "<prompt>"
```

This has not been tried here. The first runs found that the CLI's login does
not survive an isolated `HOME`; whether an API key in the environment is enough
is untested. Until someone reports it working, treat the bias described in
[Limits](./README.md#the-runs-were-not-made-in-a-neutral-environment) as open.
