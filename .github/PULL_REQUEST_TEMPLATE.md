<!--
Thanks for contributing. Please branch from an up-to-date `main`: the repository
requires branches to be current before merging, and several recent fixes turned
out to be already merged. Keep one logical change per PR.
-->

## What this changes

<!-- What is different after this PR, and why. If it fixes an issue, say `Closes #123`. -->

## How I verified it

<!--
Which of these you ran, and what you observed. Delete lines that do not apply.
Backend: cd backend && pytest tests/
Frontend: cd frontend && npm run lint:check && npm run format:check && npx vitest run
-->

- [ ] Backend tests pass
- [ ] Frontend lint, format and tests pass
- [ ] I ran the change in the real app (dev stack or a packaged build) on: <!-- macOS / Windows / Linux, GPU or CPU -->

## Notes for the reviewer

<!--
Anything that needs a second pair of eyes: a decision you were unsure about, a
behaviour that changed on purpose, a platform you could not test on.

Changes to engine code (backend/src/engines/) need a run on the platform they
touch: MLX on Apple Silicon, llama-server on Windows/Linux.
-->
