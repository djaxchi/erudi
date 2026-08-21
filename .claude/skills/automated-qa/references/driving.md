# Driving the packaged app over CDP

## The driver

A stateless script that attaches to the running app and executes a JS body with
`page` in scope. Stateless matters: each scenario runs in its own invocation, so
a failure never leaves the driver in a state that corrupts the next scenario.

```js
// drive.mjs — node drive.mjs "<js body with `page` in scope>"
import { chromium } from '<repo>/frontend/node_modules/playwright-core/index.mjs';

const body = process.argv[2];
const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
let page = null;
for (const ctx of browser.contexts()) {
  for (const p of ctx.pages()) {
    if (!p.url().startsWith('devtools://')) page = p;   // skip the DevTools page
  }
}
if (!page) { console.error('no app page found'); process.exit(1); }
try {
  const fn = new Function('page', `return (async () => { ${body} })()`);
  await fn(page);
} catch (e) {
  console.error('DRIVE_ERROR:', e.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
```

Use `playwright-core` from the repo's `frontend/node_modules` rather than
installing anything — it is already there.

## Verifying state, which is the part that matters

Always read state back after an action that changes it:

```js
const sw = page.locator('[role="switch"], [aria-checked]').first();
await sw.click();
console.log('after click:', await sw.getAttribute('aria-checked'));
```

For model selection specifically, confirm through the backend rather than the
DOM: create the conversation, then check which model it actually bound to. The
UI can show a selection that never reached the request.

```bash
curl -s http://127.0.0.1:27182/erudi/conversations/<id> | python3 -c "
import json,sys; d=json.load(sys.stdin); print('llm_id', d.get('llm_id'))"
```

The backend log is the other source of truth. It states the turn mode and which
tools were on the turn, which is how you confirm an agentic scenario actually
ran agentically rather than falling back to plain.

## Finding elements

Enumerate what is on the page before guessing selectors:

```js
const icons = await page.locator('svg').evaluateAll(els =>
  els.map(e => e.getAttribute('class'))
     .filter(c => c && c.includes('lucide'))
     .map(c => c.match(/lucide-[a-z-]+/)?.[0]));
console.log([...new Set(icons)]);
```

Beware selectors that match more than you think — a generic icon class can match
a dozen elements, and clicking `.first()` then hits a row control instead of the
dialog button you meant. Scope to the dialog, or match on the accessible name
with `{ name: 'Delete', exact: true }`.

Settings and per-conversation controls live behind a collapsible panel; open it
before asserting the control is absent.

## Drag and drop

`setInputFiles` does not work for drag-and-drop in Electron: files injected
through CDP have no OS path, and the app needs one. Dispatch a real drag event
carrying the path instead:

```js
const client = await page.context().newCDPSession(page);
await client.send('Input.dispatchDragEvent', {
  type: 'drop', x, y,
  data: { items: [{ mimeType: 'application/pdf', title: 'doc.pdf', path: '/abs/path/doc.pdf' }],
           files: ['/abs/path/doc.pdf'], dragOperationsMask: 1 },
});
```

## Waiting

Wait on conditions, not durations. Poll the API for the state the scenario needs
(a job status, a message with content, a model marked installed) rather than
sleeping a guessed number of seconds. First-turn latency includes loading the
model into memory and is legitimately long.

```bash
until curl -s .../conversations/<id> | python3 -c "..."; do sleep 5; done
```
