# Test strategy — LangChain conversation/arena refactor (PR1)

> **Status: DRAFT for agreement.** Validates the PR1 socle (agent runner + SQLite
> checkpointer + summarization + arena) on the **Gemma3 270M** model.

## The pyramid, applied

- **Unit** (done, P0–P7): each unit isolated, engine/model faked
  (`GenericFakeChatModel`, mocked engine). No UI, no real model.
- **Integration** (pytest, **no browser**): real components across a boundary — service
  + repository + real SQLite + real LangGraph checkpointer + real `create_agent` graph,
  exercised via direct calls or FastAPI `TestClient`. Asserts on real DB / checkpointer
  state. This is where LangChain `thread_id` correctness, B3 purge, persistence,
  summarization compaction, and alternation-after-error are proven.
- **E2E** (Playwright, **browser, black-box**): the whole app through the real UI.
  Asserts **only on what the user observes** — never reaches into the DB. The proof of
  context is *the bot's own answer*.

> **Rule we will not break:** an E2E test asserts observable behaviour; it does not
> open the DB to check internals. Internals are the integration layer's job.

---

## Layer 0 — Pre-flight: context-engineering probe (do FIRST)

Before any scenario, rule out a prompt/template bug (a weak-but-instruction-tuned 270M
*should* obey trivial instructions; if it doesn't, our context engineering is suspect —
leading hypothesis: **Gemma has no `system` role**, so our `SystemMessage` may be
mis-rendered).

- **P0.1** Confirm `data/models/191` identity (config/README): is it gemma3-270m-**it**?
- **P0.2** Barebones probe via the engine: "Repeat exactly: SUN" **without** any system
  prompt → must return "SUN". Establishes baseline instruction-following.
- **P0.3** Same probe **with** our tiny-tier system prompt → compare. If it degrades,
  the system prompt / its rendering is the culprit.
- **P0.4** Inspect what the tokenizer's chat template actually produces from
  `[SystemMessage, HumanMessage]` for this model (does Gemma accept/merge/drop `system`?).
- **Outcome:** if a bug is found (e.g. Gemma needs system merged into the first user
  turn, or the tiny prompt is counter-productive) → **fix it in PR1** before E2E.

### ✅ Findings (2026-06-01) — context engineering is SOUND, no fix needed
- **P0.1** Model 191 = `google/gemma-3-270m-it` (instruction-tuned, 4-bit).
- **P0.4** Gemma's chat template **merges `system` into the first user turn**
  (`first_user_prefix`) — our `SystemMessage` is correctly included, no bug. (Template
  also enforces strict user/model alternation via `raise_exception` — matches our M2
  guard.)
- **P0.2 / P0.3** "Repeat exactly: SUN" → `SUN` **both** with and without our system
  prompt — instruction-following works; the system prompt doesn't degrade it.
- **P0.5** 2-turn recall ("Remember SUN" → "What word?") → `SUN` — **multi-turn context
  works at the model level**.
- **Root cause of the earlier "generic" live answer**: a bad probe prompt
  ("My name is Rayan. Reply in one short sentence.") with no concrete task → the tiny
  model paraphrased its system prompt. **Not** a context-engineering bug.
- **Implication for E2E:** use clear, concrete instructions/questions (not vague
  statements). Context scenarios (E2/E3/E4/E12) are valid as black-box.

---

## Layer 1 — Integration tests (pytest, backend, no browser)

Most already exist from P0–P7; (NEW) marks ones to add.

- **IT1 — Persist + thread mapping.** A query persists exactly `[user, llm]` rows and a
  checkpointer thread keyed by `str(conversation_id)` == `[human, ai]`. *(have)*
- **IT2 — Multi-turn restoration.** Two turns → thread `[human, ai, human, ai]`; only the
  new message is passed in (history restored from the checkpointer). *(have)*
- **IT3 — thread_id isolation.** Two conversations → each thread contains only its
  own messages; no cross-thread bleed. ✅ `test_thread_id_isolation_no_cross_bleed`
- **IT4 — Delete purges checkpointer / BLOCKER B3 (service-level).**
  `service.delete_conversation` removes rows **and** `adelete_thread` the checkpointer
  thread (`aget_tuple` → None). ✅ `test_delete_conversation_purges_checkpointer_thread`
- **IT5 — No resurrection on id reuse (B3).** Purge + reuse same thread_id → fresh
  thread, deleted history never reappears. ✅ `test_purged_thread_starts_fresh_no_resurrection`
- **IT6 — On-disk persistence across restart.** Write to a file, close, reopen the same
  file → thread state survives. ✅ `test_checkpoint_state_survives_reopen_on_disk`
- **IT7 — Summarization compaction.** Past threshold → thread compacted to a summary;
  `Message` rows untouched. ✅ `test_summarization_compacts_checkpointer_state`
- **IT8 — Alternation repair after error / MAJOR M2.** Failed turn leaves no dangling
  `human`; next turn has valid alternation. ✅ `test_repair_alternation_appends_ai_after_dangling_human`
- **IT9 — Error sentinel, no traceback / G1 (service-level).** Forced failure persists an
  `llm` message with `[ERROR_MESSAGE_SYSTEM]`, no traceback, no leaked internals.
  ✅ `test_query_failure_persists_sentinel_without_traceback`
- **IT10 — Title-gen & arena are stateless.** Neither creates a checkpointer thread
  (arena constructs `AgentRunner(checkpointer=None)`). ✅ `test_arena_mode_runs_without_checkpointer`
- **IT11 — Generation guard holds mid-stream + serializes.** Active marker held for the
  whole runner stream; concurrent generations don't interleave.
  ✅ `test_astream_holds_active_marker_across_whole_stream` + `test_guard_serializes_concurrent_generations`

> **Layer 1 status (2026-06-01): all green.** 72 passed across the agents/conversation/arena
> suite (`test_agent_runner`, `test_conversations`, `test_arena`, `test_checkpointer_wiring`,
> `test_engine_generation_guard`, `test_agent_prompts`, `test_langchain_imports`). ruff + compileall clean.

---

## Layer 2 — E2E tests (Playwright, black-box, UI only)

> Proof = the app's visible behaviour + the bot's answers. Streaming is verified by the
> bubble **growing across successive snapshots**, never a single final blob. Scenarios
> marked *(UI?)* depend on the control being exposed — confirmed during the run.

### Core chat: streaming & context (the heart)
- **E1 — Streaming reply.** New conversation → "Count from 1 to 10." → reply streams
  token-by-token into the bubble; completes.
- **E2 — Context recall.** "Remember this word: SUN." → reply. "Repeat the word I gave
  you." → answer contains **SUN**.
- **E3 — Follow-up.** Ask something → "Say that again." / "Continue." → coherent
  continuation referencing the prior turn.
- **E4 — Deep reference.** "Translate your previous answer into French." → operates on
  the previous turn (strong proof the history is in context).

### Conversation management
- **E5 — Title appears.** First message → sidebar title goes "New Conversation" → a
  generated short title.
- **E6 — New conversation is blank.** Create new → empty; "What did we talk about?" →
  nothing prior.
- **E7 — History persists on reload.** Send messages → reload `localhost:3000` → all
  messages still rendered, ordered.
- **E8 — Switch conversations.** Sidebar A ↔ B → each shows only its own messages.
- **E9 — Rename conversation *(UI?)*.** Rename → new name shown + survives reload.
- **E10 — Delete conversation.** Delete → disappears from the list.
- **E11 — Bulk delete *(UI?)*.** Select several → delete → all removed.

### Isolation
- **E12 — Two conversations don't mix.** A: "My city is Paris." B: "My city is Tokyo."
  Ask each "What is my city?" → A=Paris, B=Tokyo (no leak, proven by answers).

### Message-level actions
- **E13 — Star a message *(UI?)*.** Star → stays starred after reload.
- **E14 — Unstar *(UI?)*.** Unstar → reverts.
- **E15 — Delete a single message *(UI?)*.** Delete one → removed; conversation continues.

### Parameters & customization (also context-engineering proof)
- **E16 — Custom prompt obeyed.** Set conversation custom prompt "Always answer in
  French." → subsequent answers are in French. *(black-box proof the system/custom prompt
  is plumbed correctly — directly tied to Layer 0.)*
- **E17 — Param change *(UI?)*.** Change temperature/max tokens → still generates, no
  error.
- **E18 — Switch model *(UI?)*.** Change the conversation's model → next message uses it.

### Errors & resilience
- **E19 — Error renders.** Force a generation failure (stop the model server
  mid-stream) → an error turn renders (the `[ERROR_MESSAGE_SYSTEM]` styling).
- **E20 — Recovery after error.** Send a normal message after E19 → it streams a normal
  reply (no broken stream, no "roles must alternate").

### Arena
- **E21 — Arena single model streams.** Arena → pick a model → send → tokens stream into
  the panel.
- **E22 — Arena duel (2 panels).** Two panels, one prompt → both produce a reply.
- **E23 — Arena custom prompt *(UI?)*.** Custom prompt per panel → reflected in the
  answer.

---

## Layer 2 — Execution results (2026-06-01, Gemma-270M, browser→renderer)

Driven via Playwright over the renderer at `http://localhost:3000` (Chromium with
web-security/CSP/Local-Network-Access disabled to replicate Electron's session —
see Setup). Real stack: MLX → ChatOpenAI → AsyncSqliteSaver.

- **E1 — Streaming** ✅ in-process length series grew 937→1468 over ~1.3 s
  (token-by-token bubble growth in the rendered DOM); coherent answer.
- **E2 — Context recall** ✅ "Remember SUN" → next turn "What word?" → **SUN**.
- **E5 — Auto-title** ✅ "Paris, City of Light", "Paris, City", "Tokyo City".
  ⚠️ instruction-style first messages can yield junk titles (e.g. a fenced
  ` ```json ` repetition) — tiny-model quirk on atypical input, not a pipeline bug.
- **E7 — Reload persistence** ✅ hard reload of a 6-message conversation
  re-renders every message (fetched from the Message table).
- **E8 — Switch conversations** ✅ navigating between threads shows each its own
  history.
- **E12 — Isolation** ✅ conv A "city=Paris" → "Paris"; conv B "city=Tokyo" →
  "Tokyo"; no cross-thread bleed (proven by the answers).
- **Bonus — backend-restart persistence** ✅ conversations survive a full backend
  restart (on-disk business SQLite + checkpointer).

**Regression found & fixed during E2E:** the ChatOpenAI path dropped the engine's
`repetition_penalty=1.2` / `repetition_context_size=5` (always applied by the old
`generate_stream`), making even Gemma-270M loop on trivial prompts ("count to 20"
→ a repeating phrase). Restored in `model_factory.build_chat_model` via
`ChatOpenAI.extra_body`, with per-engine wire-name translation
(`_translate_payload_kwargs`: MLX native, llama.cpp → `repeat_penalty` /
`repeat_last_n`). Frontend default `temperature` 1.0→0.2 (aligns with backend;
small models stay coherent). Covered by 2 unit tests.

**Not runnable (UI not implemented):** E11 bulk-delete, E15 delete-single-message.
**Covered at Layer 1 instead of UI:** E19/E20 error + recovery (IT8/IT9),
delete + B3 purge (IT4). Arena (E21–E23) validated via the API (the repetition fix
applies there too).

## Setup
- **Backend**: `cd backend && source venv/bin/activate && python run.py --port 27182`.
- **Renderer**: webpack dev server `http://localhost:3000` (HashRouter `/#/erudi/...`);
  Playwright drives it; streaming is `fetch` to `127.0.0.1:27182`.
- **Browser security (critical for a plain browser):** in Electron, `main.js`
  (`onHeadersReceived`) overrides the dev CSP and the runtime ignores Chromium's
  Local Network Access checks, so the renderer can call the loopback backend. A
  plain Chromium does NOT — it enforces (a) the dev server's restrictive
  `Content-Security-Policy` header (no `connect-src` → blocks `127.0.0.1:27182`)
  and (b) `ERR_BLOCKED_BY_LOCAL_NETWORK_ACCESS_CHECKS` (loopback from a
  `localhost` origin). Both are defeated by launching Chromium via
  `.playwright/cli.config.json` with `contextOptions.bypassCSP=true` and
  `launchOptions.args` = `--disable-web-security` +
  `--disable-features=…LocalNetworkAccessChecks,BlockInsecurePrivateNetworkRequests…`.
  (Test-harness only — NOT shipped; the real app uses the Electron session config.)
- **Model**: Gemma3 270M seeded as a local `Llm` (visible in the UI picker).

## Out of scope
- KB RAG retrieval quality (KB migration is **PR2**).
- Packaged PyInstaller build (separate validation).
- Answer-quality assertions beyond instruction-following (270M is small — but it must
  still obey trivial instructions, per Layer 0).
