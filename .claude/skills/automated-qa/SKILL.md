---
name: automated-qa
description: Run a release-candidate QA pass on Erudi by installing the real packaged app and driving it through CDP, scenario by scenario from QA-SCENARIOS.md. Use this whenever the user asks for a QA pass, says "fais la QA", asks you to validate a draft or release candidate, wants scenarios verified on a build, or asks whether a candidate is shippable. Also use it after cutting a new draft, since a draft that has not been driven through the real app has not been validated at all.
---

# Automated QA on the packaged app

The point of this pass is to test **what ships**, not what runs in dev. Most of
the defects worth catching only exist in the packaged build: frozen-import
behaviour, bundled binaries, the real data directory, the updater, and the
Electron main process spawning a real backend executable. A dev-mode run cannot
see any of them.

The pass is the same on every platform; only the setup and the process names
differ. `references/platforms.md` holds every OS-specific path and command —
consult it rather than assuming the macOS layout.

## Non-negotiables

**Drive the installed app.** Install the artifact from the draft, launch it like
a user would, and drive it over CDP. Never substitute `npm start`, never
substitute headless, never call the API directly *as a replacement* for a
scenario — API calls are for verifying what the UI claims, not for skipping it.

**Start from a clean machine state.** A QA pass on top of a previous install
tests a migration, not an install. Remove the installed app and the data
directory before installing, after checking no Erudi process is running. Say
what you are removing before you remove it — that directory holds real models,
conversations and knowledge bases. Note that the Electron logs live *outside*
the data directory on every platform and survive a reinstall: filter them by
today's date, or an old run's lines will be read as this run's.

**Verify UI state after every action that changes it.** This is the single
lesson that cost the most time: a model picker that silently did not stick sent
a whole run of conversations to the wrong model, producing "failures" that were
entirely an artifact of the driving script. After selecting a model, opening a
panel, or toggling a setting, read the state back and confirm it took. When a
scenario fails, prove the app was actually in the state the scenario assumes
before reporting the failure.

**Investigate every finding before reporting it.** A symptom is not a report.
Read the backend log, check the request in the network trace, look at the code
path. Distinguish a product defect from a driving artifact from an environment
problem. Reporting all three as "bugs" destroys the credibility of the pass.
Half of the false alarms so far were **selector artifacts** — see
`references/pitfalls.md` before concluding that something "is not displayed".

**Do not open issues unless the principal has said to.** The default is to
record findings and report them; the principal decides what becomes an issue,
and in what form. When they do delegate that, one issue per distinct defect,
with the log lines and the code pointer, and reproductions of *known* issues go
as comments on the existing issue, never as duplicates.

## Setup

The shape is identical everywhere — the exact commands per OS are in
`references/platforms.md`:

1. **Confirm nothing is running** — no Erudi process, no embedded `postgres`,
   no inference child, nothing on port 27182. A leftover from a previous run
   changes what the build under test does.
2. **Check free disk before downloading anything.** A pass costs the installer,
   the installed app and at least one multi-gigabyte model; keep a few GB of
   headroom or the session locks up (see pitfalls).
3. **Clean state** — inventory the data directory, then remove it and the app.
4. **Install from the draft** — download the platform artifact with
   `gh release download`, install it the way a user would, and **delete the
   installer only after the app is verified in place** (a copy that silently
   failed plus an eager delete means downloading again).
5. **Verify the artifact** — version string, signature/notarization where the
   platform has one.
6. **Launch with the debugging port** — `--remote-debugging-port=9222` — and
   wait for `curl -s http://127.0.0.1:9222/json/version` to answer, then for
   `/erudi/health` to return 200 (follow redirects: the route answers 307 on
   the bare path). A first run pays for database initialisation and catalog
   seeding; it is still a few seconds, not minutes.

## Driving

Use a small stateless driver that attaches over CDP and runs a JS body with
`page` in scope — see `references/driving.md` for the script and the
interaction patterns that work in Electron (custom pickers, hash navigation,
hover-revealed row controls, and drag-and-drop, which needs real file paths and
does not work through the usual file-input route).

Keep each scenario's driving separate and idempotent. When something fails,
being able to re-run that one scenario alone is worth more than a fast full run.

## Order of the pass

1. **Regression gate first.** Anything the candidate exists to fix — list the
   merged fixes since the previous draft and verify each one on the real build
   before anything else. If a previous release blocker still reproduces, stop
   and report — the rest of the pass is wasted effort on a build that will not
   ship.
2. **Critical functional path**: first launch, catalog, download a model, chat,
   streaming, persistence across relaunch.
3. **The scenarios in `QA-SCENARIOS.md`**, section by section. That file is the
   source of truth; if a scenario is missing for behaviour that shipped, add it
   rather than testing from memory.
4. **Model-free scenarios can run without any model on disk** — deletion flows,
   orphaned conversations, quit/relaunch persistence, hard-kill and orphans,
   window-close behaviour, updater silence on a draft, security headers,
   settings. Group them so the machine can be handed back (models deleted,
   nothing loaded) while they run.
5. **Vision scenarios last**, because they need a different model. Delete the
   model on disk first to make room — the delete flow is itself a scenario —
   then download a vision-capable one.
6. **Leave for a human what needs a human**: cutting the network for the
   offline block, and anything that only exists after promotion (the update
   banner). Hand those over with step-by-step instructions and the expected
   result of each step, not a pointer to the scenario file.

## Model hygiene

Models are multi-gigabyte and the machine is shared with everything else.

- Keep **at most one** model on disk at any time. Delete before downloading the
  next one, never after.
- Never run two models simultaneously — one inference server at a time.
- Use models of at least ~4B for agentic, KB and reasoning scenarios. Smaller
  models fail those for reasons of capability rather than defect, which produces
  findings that are not about the product. Say which model produced each result.
- A thinking model that is also tool-capable (Qwen3 family) covers the reasoning
  strip, the agentic KB block and web search in one download; a small VL model
  (Qwen2.5-VL-3B) covers vision, re-bind and a second KB assistant in another.
- Delete what you downloaded when the pass is done, and whenever the user asks
  for their machine back: unloading = deleting the model through the UI, which
  also terminates the inference child.

## Reporting

Report per scenario: pass, fail, or blocked, and for anything that is not a pass,
the investigated cause. Separate:

- **Product defects** — reproduce in the app, with the code path or log line.
- **Driving artifacts** — the script's fault; fix the script, re-run, do not
  report as a defect.
- **Environment problems** — leaked processes, exhausted resources, stale state.

Lead the report with whether the candidate is shippable, then the blocking
findings, then the rest. That is the decision the principal is trying to make.
State the build SHA and the platform/hardware on the first line; a finding
without them cannot be reproduced by the next person.

## References

- `references/platforms.md` — per-OS paths, install/uninstall/launch commands,
  process names, and where the logs are.
- `references/driving.md` — the CDP driver, Electron interaction patterns, and
  how to verify UI state.
- `references/pitfalls.md` — failure modes that have wasted time before, and how
  to recognise them early.
