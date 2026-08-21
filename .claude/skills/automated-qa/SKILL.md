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

## Non-negotiables

**Drive the installed app.** Install the artifact from the draft release, launch
it like a user would, and drive it over CDP. Never substitute `npm start`, never
substitute headless, never call the API directly *as a replacement* for a
scenario — API calls are for verifying what the UI claims, not for skipping it.

**Start from a clean machine state.** A QA pass on top of a previous install
tests a migration, not an install. Remove `/Applications/Erudi.app` and
`~/Library/Application Support/erudi` before installing, after checking no Erudi
process is running. Say what you are removing before you remove it — that
directory holds real models, conversations and knowledge bases.

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

**Do not open issues.** Record findings and report them. The principal decides
what becomes an issue, and in what form.

## Setup

```bash
# 1. Confirm nothing is running
pgrep -fl "Erudi|erudi"; lsof -ti :27182

# 2. Clean state (inventory first, then remove)
du -sh ~/Library/Application\ Support/erudi
rm -rf /Applications/Erudi.app ~/Library/Application\ Support/erudi

# 3. Install from the draft
gh release download v<version> --pattern "*arm64.dmg" --dir <scratchpad>
hdiutil attach <scratchpad>/Erudi-<version>-arm64.dmg
cp -R "/Volumes/Erudi <version>/Erudi.app" /Applications/
hdiutil detach "/Volumes/Erudi <version>"

# 4. Launch with the debugging port so CDP can attach
open -a Erudi --args --remote-debugging-port=9222
```

Wait for `curl -s http://127.0.0.1:9222/json/version` to answer before driving.
The backend takes noticeably longer on a first run because of the one-time
database initialisation.

## Driving

Use a small stateless driver that attaches over CDP and runs a JS body with the
page in scope — see `references/driving.md` for the script and the interaction
patterns that work in Electron (including drag-and-drop, which needs real file
paths and does not work through the usual file-input route).

Keep each scenario's driving separate and idempotent. When something fails,
being able to re-run that one scenario alone is worth more than a fast full run.

## Order of the pass

1. **Regression gate first.** Anything the candidate exists to fix. If a
   previous release blocker still reproduces, stop and report — the rest of the
   pass is wasted effort on a build that will not ship.
2. **Critical functional path**: first launch, catalog, download a model, chat,
   streaming, persistence across relaunch.
3. **The scenarios in `QA-SCENARIOS.md`**, section by section. That file is the
   source of truth; if a scenario is missing for behaviour that shipped, add it
   rather than testing from memory.
4. **Vision scenarios last**, because they need a different model. Delete the
   models on disk first to make room, then download a vision-capable one.

## Model hygiene

Models are multi-gigabyte and the machine is shared with everything else.

- Keep **at most one** on disk at any time. The machine this runs on is close to
  full, so a second multi-gigabyte model is not a convenience, it is what makes
  the next write fail. Delete the current one before downloading the next.
- Never run two models simultaneously — one inference server at a time.
- Use models of at least ~4B for agentic, KB and reasoning scenarios. Smaller
  models fail those for reasons of capability rather than defect, which produces
  findings that are not about the product.
- Delete what you downloaded when the pass is done.

## Reporting

Report per scenario: pass, fail, or blocked, and for anything that is not a pass,
the investigated cause. Separate:

- **Product defects** — reproduce in the app, with the code path or log line.
- **Driving artifacts** — the script's fault; fix the script, re-run, do not
  report as a defect.
- **Environment problems** — leaked processes, exhausted resources, stale state.

Lead the report with whether the candidate is shippable, then the blocking
findings, then the rest. That is the decision the principal is trying to make.

## References

- `references/driving.md` — the CDP driver, Electron interaction patterns, and
  how to verify UI state.
- `references/pitfalls.md` — failure modes that have wasted time before, and how
  to recognise them early.
