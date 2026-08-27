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
installing anything — it is already there on every platform the repo builds on.

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
curl -s -L http://127.0.0.1:27182/erudi/conversations/<id> | python3 -c "
import json,sys; d=json.load(sys.stdin); print('llm_id', d.get('llm_id'))"
```

The backend log is the other source of truth. It states the turn mode
(`Turn mode: agentic KB (...)` / `plain`), which tools were on the turn, and
every `Tool invoked: ...` line — which is how you confirm an agentic scenario
actually ran agentically rather than falling back to plain, and whether a
"not in the documents" answer was preceded by a search at all.

## Finding elements

Enumerate what is on the page before guessing selectors:

```js
const icons = await page.locator('svg').evaluateAll(els =>
  els.map(e => e.getAttribute('class'))
     .filter(c => c && c.includes('lucide'))
     .map(c => c.match(/lucide-[a-z-]+/)?.[0]));
console.log([...new Set(icons)]);
```

And when a locator counts zero, dump the neighbourhood before deciding the thing
is absent:

```js
const html = await page.getByText('Some label').first()
  .locator('xpath=ancestor::div[2]').evaluate(e => e.outerHTML.slice(0, 800));
```

Beware selectors that match more than you think — a generic icon class can match
a dozen elements, and clicking `.first()` then hits a row control instead of the
dialog button you meant. Scope to the dialog, or match on the accessible name
with `{ name: 'Delete', exact: true }`.

Settings and per-conversation controls live behind a collapsible panel; open it
before asserting the control is absent.

## Patterns specific to this app

**Overlays and modals** are `div.fixed.inset-0` with no ARIA role — the Welcome
modal, download confirmations, delete confirmations. Scope button clicks to the
overlay: `page.locator('div.fixed.inset-0').first().locator('button', { hasText: 'Download' })`.

**The model picker** (Chat, Arena, conversation header) is a
`div[title="<model name>"]`; click it, then click the option by text, then read
`getAttribute('title')` back:

```js
await page.locator('div[title]').first().click();
await page.getByText('Aerolith Assistant', { exact: true }).first().click();
console.log(await page.locator('div[title]').first().getAttribute('title'));
```

**History rows** (`div.relative.group` in the sidebar) reveal a `lucide-pen-line`
(rename) and a `lucide-x` (delete) `<svg>` on hover. Hover the row, click the
svg, then confirm in the overlay.

**Installed cards** carry `button[title="Delete model"]`; catalog cards carry a
`Download` button that becomes a disabled `Installed` once the model is on disk.
The assistant-name lock on the KB screen is `button[title="Validate and lock name"]`.

**The rail hides the Chat link while you are in a conversation** (it is the
active entry). Navigate by hash instead of hunting for the link:

```js
await page.evaluate(() => { location.hash = '#/erudi/chat'; });
```

**"See all"** on a carousel toggles its label to "Show less"; every card is in
the DOM either way, so count the label change, not the cards.

## Drag and drop

`setInputFiles` does not work for drag-and-drop in Electron: files injected
through CDP have no OS path, and the app needs one. Dispatch a real drag event
carrying the path instead. Each item needs a `data` field or CDP rejects the
call with "Invalid parameters":

```js
const client = await page.context().newCDPSession(page);
const f = '/abs/path/doc.txt';
const payload = { items: [{ mimeType: 'text/plain', title: 'doc.txt', data: 'x', baseURL: 'file://' + f }],
                  files: [f], dragOperationsMask: 1 };
await client.send('Input.dispatchDragEvent', { type: 'dragEnter', x, y, data: payload });
await client.send('Input.dispatchDragEvent', { type: 'drop', x, y, data: payload });
```

Dropping the same path twice is the de-duplication scenario; the list count and
the confirmation dialog's file count must agree.

## Waiting

Wait on conditions, not durations. Poll the API or the log for the state the
scenario needs (a job status, a `Query completed for conversation N` line, a
model marked installed) rather than sleeping a guessed number of seconds.
First-turn latency includes loading the model into memory and is legitimately
long.

```bash
until grep -q "Query completed for conversation 3" <log>; do sleep 4; done
```

Match on today's date or a monotonic counter: `grep -c "Query completed"` across
a log that survived a reinstall counts last week's turns too.
