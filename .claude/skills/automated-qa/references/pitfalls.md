# Pitfalls

Failure modes that have already cost time. Recognising them early is worth more
than any amount of careful driving.

## The false alarm that looks like a product defect

**Symptom seen**: a run of conversations showed no tool calls at all and answers
that ignored the knowledge base — apparently a serious agentic regression.

**Actual cause**: the driving script's model selection never stuck. Every
conversation had been created against a different model, one with no KB and no
tool capability. The product was fine.

**How it was found**: checking `llm_id` on the conversation and the turn-mode
line in the backend log, which said `plain` where the scenario assumed agentic.

**The rule**: before reporting that a feature did not fire, prove the app was in
the state the scenario requires. Most "the feature is broken" findings are "the
feature was never enabled for that turn".

## "It is not displayed" — the selector was wrong

Three findings in one pass were dead on arrival because the selector did not
match what the app renders:

- **The Welcome modal has no `role="dialog"`** — it is a plain `div.fixed.inset-0`
  overlay. `[role="dialog"]` counted zero and looked like "the dialog did not
  show". The backend log said `Welcome popup marked as displayed (first time)`
  for a `fe-…` request, which is what proved the modal *had* rendered.
- **The model picker is not a `<select>`** — it is a `div[title="<model name>"]`
  that opens a list on click. `selectOption` cannot touch it.
- **History rows reveal `pen-line` and `x` icons on hover, not a trash button**,
  and they are bare `<svg>`s, not `<button>`s.

**The rule**: when a count is zero, dump the DOM around where the element should
be (`outerHTML.slice(0, 800)`) before concluding anything. Reading the component
source (`frontend/src/components/...`) takes thirty seconds and settles it.

## `pgrep -f` matches the shell that runs it

Any pipeline whose command line contains the pattern — `grep no-sandbox`,
`pgrep -f mlx` — finds its own shell and reports a survivor that does not exist.
A "2 renderer processes run with --no-sandbox" finding on macOS was two copies of
the grep itself. Match on executable paths (`Erudi.app/Contents/MacOS`,
`pginstall/bin/postgres`, `Erudi Helper (Renderer)`) and read the full `ps -o
command=` of anything that matches before believing it.

## Environment exhaustion masquerading as failures

**Symptom seen**: a test suite reporting several failures and taking twenty-five
times its normal runtime.

**Actual cause**: the system's SysV shared-memory segment table was full of
orphans from killed database clusters, so `initdb` could not start. Nothing was
wrong with the code.

```bash
ipcs -m | awk '/^m /{print $2}' | wc -l          # against kern.sysv.shmmni (32)
ipcs -m | awk '/^m /{print $2}' | xargs -n1 ipcrm -m
```

**The rule**: when failures are numerous, slow and diverse, suspect the machine
before the code. Especially after killing processes, running concurrent suites,
or interrupting anything that owns a cluster.

## Leaked processes between runs

A killed app can leave the backend, `postgres` or an inference server running.
The next launch then meets an occupied port or a live cluster, and behaves in
ways that have nothing to do with the build under test. Check before every
install and after every forced kill — commands per OS in `platforms.md`. A
system-wide PostgreSQL (Homebrew, a service on 5432/5434) is not ours: check the
executable path before reporting an orphan.

## Dialogs freeze the driver

A native or JS modal blocks CDP entirely — the session stops responding and
looks hung. Avoid triggering confirmation dialogs blindly; when a scenario needs
one, know which button you are about to press and scope the selector to the
dialog. The app's own confirmations are in-page overlays and are safe; OS-level
dialogs (file pickers, permission prompts) are not.

## Small models failing capability, not correctness

A 0.5B model will not reliably call a tool, ground an answer, or follow an
instruction to cite a source. Running agentic or KB scenarios against one
produces findings that describe the model, not the product. Use a model of at
least ~4B for anything involving tools, retrieval or reasoning, and say which
model produced each result in the report.

Conversely, a real product defect can hide behind "the model was just being
dumb": an 8B model that answers "not in your documents" *without any `Tool
invoked` line in the log* is not a model failure, it is a search that never ran.
The log line is the discriminator, every time.

## First-run costs look like hangs

A fresh install pays for database initialisation, catalog seeding, and — on the
first knowledge-base use — a several-hundred-megabyte embedding-model download.
The first chat turn also loads the model into memory (twenty-plus seconds for an
8B on Apple Silicon). Each of these can look like a hang to an impatient driver.
Wait on the actual condition and check the backend log for progress before
concluding anything is stuck.

## Running the machine out of disk

A pass adds an installer, a ~1.2 GB app and a multi-gigabyte model, and that is
enough to hit zero free bytes on a full laptop — at which point **every tool that
writes fails**, including the shell itself, because the harness creates a
capture file before running the command. There is then no way to free space
from inside the session.

Avoid it rather than recover from it:

- `df -h` **before** downloading anything, and again before each model.
- Delete the installer right after the install is *verified* — and only then.
  An unconditional `rm` chained after a `cp` that silently failed (the DMG's
  volume name was not what the script assumed) cost a second 420 MB download.
- Delete the current model before downloading the next one, never after. When a
  scenario needs a model bigger than the free space, the delete-model flow is
  itself a QA scenario — run it to make room instead of freeing space by hand.
- Free space is not stable: APFS purgeable space and a staged OS update can
  swallow several GB between two `df` calls. Read the number, do not remember it.

## Old logs survive the clean step

The Electron logs (`main.log`, `backend.log`) live in the OS log directory, not
in the data directory that the clean step removes, and electron-log appends
across reinstalls. A count of "27 welcome-popup calls" was 26 from a run a week
earlier. Filter on today's date before treating a log as this run's.

## The Chat page and the Installed card disagree about a weights-missing assistant

After deleting a base model with "Delete anyway", the assistant's Installed card
correctly shows "Model weights missing" with Chat disabled — but the Chat page's
picker still auto-selects it and lets a message through to a clean failure
(#376). Do not mistake the resulting error for the delete flow being broken; the
delete flow is fine, the entry path is the gap.

## Reporting a laptop number

Local failure counts carry local noise: worktree caches, concurrent agents,
leaked state. When a number will be read by someone else or written into an
issue, quote CI's, and say explicitly when a figure is from a developer machine.
