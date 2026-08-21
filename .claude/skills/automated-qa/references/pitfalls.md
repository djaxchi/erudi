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
ways that have nothing to do with the build under test.

Check before every install and after every forced kill:

```bash
pgrep -fl "Erudi|erudi|postgres|llama-server|mlx_vlm"
lsof -ti :27182 :9222
```

## Dialogs freeze the driver

A native or JS modal blocks CDP entirely — the session stops responding and
looks hung. Avoid triggering confirmation dialogs blindly; when a scenario needs
one, know which button you are about to press and scope the selector to the
dialog.

## Small models failing capability, not correctness

A 0.5B model will not reliably call a tool, ground an answer, or follow an
instruction to cite a source. Running agentic or KB scenarios against one
produces findings that describe the model, not the product. Use a model of at
least ~4B for anything involving tools, retrieval or reasoning, and say which
model produced each result in the report.

## First-run costs look like hangs

A fresh install pays for database initialisation, catalog seeding, and — on the
first knowledge-base use — a several-hundred-megabyte embedding-model download.
Each of these can look like a hang to an impatient driver. Wait on the actual
condition and check the backend log for progress before concluding anything is
stuck.

## Running the machine out of disk

The startup volume on the QA machine sits close to full. A pass adds a ~400 MB
disk image, a ~1.2 GB app and a multi-gigabyte model, and that is enough to hit
zero free bytes — at which point **every tool that writes fails**, including the
shell itself, because the harness creates a capture file before running the
command. There is then no way to free space from inside the session.

Avoid it rather than recover from it:

```bash
df -h /System/Volumes/Data                 # check BEFORE downloading anything
rm -f <scratchpad>/Erudi-*.dmg             # delete the image right after installing
```

Delete the current model before downloading the next one, never after. And when
a scenario needs a model that is bigger than the free space, the delete-model
flow is itself a QA scenario — run it to make room instead of freeing space by
hand.

## Reporting a laptop number

Local failure counts carry local noise: worktree caches, concurrent agents,
leaked state. When a number will be read by someone else or written into an
issue, quote CI's, and say explicitly when a figure is from a developer machine.
