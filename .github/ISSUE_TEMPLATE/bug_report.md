---
name: Bug report
about: Report a crash, incorrect behavior, or anything that doesn't work as expected
labels: bug
---

<!-- If you have a question or need help getting started, use the Discussions tab instead of opening an issue. -->

**Describe the bug**
A clear and concise description of what's going wrong.

**To reproduce**
Steps to reproduce the behavior:

1. 
2. 
3. 

**Expected behavior**
What you expected to happen.

**Actual behavior**
What actually happened. Include error messages, logs, or screenshots if relevant.

Two log files help us diagnose issues (see [docs/logging.md](https://github.com/djaxchi/erudi/blob/main/docs/logging.md) for details):

App log (backend output + UI events):
- macOS: `$TMPDIR/erudi-backend.log` — run `echo $TMPDIR` in a terminal to resolve the folder, or use the path shown on the in-app error screen
- Linux: `/tmp/erudi-backend.log`
- Windows: `%TEMP%\erudi-backend.log`

Backend log:
- macOS: `~/Library/Logs/erudi/backend.log`
- Windows: `%LOCALAPPDATA%\erudi\logs\backend.log`
- Linux: `${XDG_STATE_HOME:-~/.local/state}/erudi/logs/backend.log`
- Running from source: `backend/logs/backend.log`

> ⚠️ Logs include conversation and message content as well as document names. Please review and redact anything private before attaching them to a public issue.

**Platform**
- OS: [e.g. Windows 11, macOS 15 Sequoia, Ubuntu 24.04]
- GPU: [e.g. NVIDIA RTX 4090, Apple M3 Pro, CPU only]
- Erudi version: [e.g. 0.4.2, or "built from source on commit abc1234"]
