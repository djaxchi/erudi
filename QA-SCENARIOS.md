# Erudi — QA Acceptance Scenarios

Walk this list on every **release candidate** (the signed *draft* build — see
[`docs/dev/release-qa-checklist.md`](docs/dev/release-qa-checklist.md) for the
process) before promoting it to `latest`.

Each line reads: **on page X, when I do Y, then Z must happen.** Tick the box if
Z happens; if it doesn't, mark it **FAIL** and open an issue. The plain language
is deliberate so anyone — not just a developer — can run the pass.

Each screen lists the **happy path** first, then **edge cases & errors** — don't
skip the edge block, that's where regressions hide. Covered: the five app
screens, the shared chrome, and non-functional behavior.

---

## Models / Explore — `/erudi/models`

**Happy path**
- [ ] When I launch the app, then I land on the Models screen and my **machine readout** shows (chip name, runtime, unified memory, GPU cores, bandwidth, inference score, and a "Sweet spot" size range).
- [ ] When at least one base model fits my machine, then a **"Recommended for your machine"** row shows up to 3 fitting models.
- [ ] When the catalog is loaded, then the left rail lists each **capability category with a live count** (General, Reasoning, Code, Vision & Multimodal, Math, Medical, Function Calling, Safety) plus Community, and clicking an entry scrolls to it.
- [ ] When I have downloaded models, then the **Installed** section lists them with Chat / Info / Knowledge Base / Delete actions.
- [ ] When I click **Download** on a runnable model and confirm, then a progress widget shows percentage, time left, cancel, and collapse; on completion the model appears in Installed.
- [ ] When I type a query in **Search Hugging Face** and press Enter, then results render ranked best-fit-first.

**Edge cases & errors**
- [ ] When it is my very first launch, then the **Welcome** dialog appears once; on later launches it does not.
- [ ] When I have no installed models, then the Installed section shows "No models installed yet…" with my recommended size.
- [ ] When no base model fits my machine, then the "Recommended" section is hidden (not empty).
- [ ] When a model is **not runnable on my hardware**, then its card shows "Not supported on your hardware" and Download is disabled.
- [ ] When a model is **gated** (from a Hugging Face search hit), then the card shows a "gated" tag.
- [ ] When a category carousel has more than 4 models, then a "See all" control expands it to a grid (and back).
- [ ] When I apply a **size filter** or **"Fits my machine"** and nothing matches, then I see "No models match these filters. Widen the size range or turn off 'Fits my machine'."
- [ ] When there are no base models at all, then the browse area shows "No base models available" (not a crash).
- [ ] When a Hugging Face search returns nothing runnable, then I see "Nothing runnable matched…" (a helpful message, not an error).
- [ ] When I am **offline** and run a Hugging Face search, then I see "No internet connection for the moment." and no request is made.
- [ ] When a download **fails**, then the widget shows the error and a "Download failed. Please try again." message.
- [ ] When I **cancel** an in-progress download, then it stops and the model returns to a not-downloaded state (no "Download failed" dialog).
- [ ] When I delete an installed model and confirm, then it is removed and a success message shows; if the delete request fails, the list is left intact with an error.
- [ ] When the network drops, then the connection pill switches from "Connected" to "Offline" live.

## Chat — `/erudi/chat`

**Happy path**
- [ ] When I open Chat with at least one local model, then the first model is auto-selected in the "Chat with" picker.
- [ ] When I type a prompt and press Enter, then it sends; Shift+Enter inserts a newline.
- [ ] When I send a prompt, then a new conversation is created and I am taken to it, where the reply **streams token by token**.
- [ ] When I adjust Creativity / Diversity / Max Tokens or customize the prompt, then those settings carry into the conversation.

**Edge cases & errors**
- [ ] When I send **without any image** (plain text), then the model answers normally.
- [ ] When I attach image(s) on a **vision-capable** model (button, paste, or drag-and-drop) and send, then thumbnails show (up to 4) and the images are used in the answer.
- [ ] When the **selected model is NOT vision-capable**, then the image **attach button is disabled** with a tooltip ("This model can't read images — pick a Vision model") and pasting/dropping an image is ignored; if an image still reaches the backend it is stripped, so the answer is plain text (never broken).
- [ ] When I try to attach a **5th** image, then it is rejected (cap of 4) and the attach button is disabled at 4.
- [ ] When I drop a **non-image** file, then it is ignored.
- [ ] When the input is **empty or whitespace** only, then the send button is disabled.
- [ ] When the model is loading on the first reply, then a "First response may take a bit longer while loading the model into memory…" hint shows.
- [ ] When I have **zero local models**, then the composer is replaced by "No current local models found, please add local models to proceed."
- [ ] When I open Chat via `?model=<name|id>`, then that model is pre-selected (else the first model stays).
- [ ] When the **backend is unreachable**, then an error dialog "Failed to load models: …" shows.

## Conversation — `/erudi/conversations/:id`

**Happy path**
- [ ] When I open an existing conversation, then its **full history** renders in order (my messages right, assistant left as markdown) and the model/settings populate.
- [ ] When I send a follow-up, then a user bubble appears immediately and the assistant reply streams live; both are saved.
- [ ] When I send the first message of a new conversation, then a short (2–4 word) **title** appears in the sidebar.
- [ ] When I reload the page, then the full text history re-renders from the database.

**Knowledge-Base / agentic behavior**
- [ ] When the model has a KB attached and is **tool-capable (agentic)**, then on a document question the model **calls the KB search tool itself** before answering, and the answer references the source.
- [ ] When an agentic, KB-attached model gets a **chit-chat / meta turn** (not about the documents), then it answers directly **without** searching the KB.
- [ ] When the model has a KB attached and is **not tool-capable (systematic)**, then relevant document excerpts are **injected up-front** every turn and the answer is grounded in them.
- [ ] When a small / uncooperative model is KB-attached, then the answer should still reference the source *(prompt-instructed only — no clickable source UI; acceptance = it mentions the doc when it complies)*.
- [ ] When KB retrieval **fails** (broken/empty vector store), then the turn **degrades to a no-context answer** instead of erroring.

**Multimodal / multi-turn**
- [ ] When I send an image on a vision model, then it is used for that turn; on the **next** turn the stale image is dropped from the model's context (only the current turn's image is sent), while the display keeps all images.
- [ ] When I reload a conversation with **file-attached** images, then the thumbnails re-render (for images still present on disk).
- [ ] When I reload a conversation whose image was **pasted from the clipboard**, then it shows an "image attachment" placeholder, not the image *(clipboard images aren't restorable yet — see #136)*.
- [ ] When an attached image's original file was **moved/deleted**, then that image quietly shows nothing on reload (no broken-image artifact).

**Edge cases & errors**
- [ ] When I hover a message, then copy and star controls appear; a starred message stays starred after reload and is fed back as context on later turns.
- [ ] When I delete the conversation I'm viewing, then it's removed and I'm redirected to `/erudi/chat`; deleting a different one keeps me in place.
- [ ] When I quit and relaunch and reopen the conversation, then its full history is intact.
- [ ] When generation **fails** or the connection **drops** mid-reply, then a red error message shows and any partial reply is kept.
- [ ] When the conversation's assigned model was **deleted**, then the backend falls back to an available model and still answers (no hard fail).

## Arena — `/erudi/arena`

**Happy path**
- [ ] When I open Arena with at least two local models, then two panels show, pre-filled with the first two models.
- [ ] When I pick a model or change settings/custom prompt in one panel, then only that panel changes.
- [ ] When I send one prompt, then it goes to **every** panel and each streams its own model's answer.
- [ ] When I click "+", then a panel is added (up to 4, layout reflows); the trash removes one (minimum 1).

**Edge cases & errors**
- [ ] When only **one** local model exists, then both panels default to it.
- [ ] When two panels use **different** models, then the answers are produced one model after another (single engine — not truly simultaneous), and the run still completes for every panel.
- [ ] When two panels use the **same** model, then the loaded model is reused (no reload between them).
- [ ] When a panel's model **errors**, then that panel shows "[Erreur]" in red while the others still resolve.
- [ ] When a panel's model has a **KB attached**, then KB context is auto-injected for that panel (no toggle).
- [ ] When I attach an **image** in Arena, then note it is currently ignored *(images dropped — see #136)*.
- [ ] When a generation is running, then settings/model pickers are disabled; there is **no stop button** — the run must finish.
- [ ] When I submit an **empty** prompt, then it does not send.

## Knowledge Base / Create Assistant — `/erudi/attach_knowledge_base`

**Happy path**
- [ ] When I open the screen, then I see the KB description, a chat-capabilities rating (my machine's inference label/score), the local-model library, a name field, and a drag-and-drop area.
- [ ] When I select a base model, type a name and **click Check to lock it**, add supported files (`.pdf`/`.txt`/`.docx`/`.xlsx`/`.csv`/`.md`), and click "Create Assistant" + confirm, then a spinner polls progress.
- [ ] When ingestion completes, then "Data attached to your Assistant successfully!" shows and the form resets.

**Edge cases & errors**
- [ ] When I leave the assistant name **unlocked** (didn't click Check), or pick no model, or add no files, then "Please fill in all required fields" shows and nothing is sent.
- [ ] When I add a **supported document** beyond `.pdf`/`.txt` (`.docx`, `.xlsx`, `.csv`, `.md`), then it is accepted; an **unsupported** file (e.g. `.png`, `.zip`) isn't offered by the picker and a dropped one is ignored.
- [ ] When I add the **same file twice**, then it is de-duplicated.
- [ ] When I submit a **scanned / image-only PDF** alongside readable files, then it is accepted as *pending vision* (no searchable content yet) and the job completes for the readable ones; a **pending-vision-only** upload fails with "no searchable content" (no OCR tier yet).
- [ ] When I submit an **empty / no-text** file (and nothing else indexes), then the job **fails** with a "no searchable content" message and the document is flagged *empty* — never a false success.
- [ ] When **every** submitted file is unreadable/unsupported, then the job fails with a clear error and the half-built assistant is auto-cleaned up.
- [ ] When **some** files fail but at least one ingests, then the job still completes for the good ones.
- [ ] When ingestion **fails** (network/HTTP), then an error dialog shows the reason.
- [ ] When the selected base model **already has a KB**, then submitting **updates** the existing KB with the new files instead of creating a new assistant.

## Shared chrome (sidebar, connection, downloads)

- [ ] When I click the sidebar icons, then I navigate to Models (Brain), Chat (Chat), Arena (Swords), and Knowledge Base (Book); the active screen is highlighted (Chat stays highlighted while in a conversation).
- [ ] When I click the bug/contact icon, then `erudi.app/contact` opens in my browser.
- [ ] When a download is in progress, then the contact icon is hidden and the sidebar is dimmed/disabled.
- [ ] When I navigate to an unknown route, then I am redirected to the Models screen.

## Non-functional (boot, offline, persistence, updates, errors)

**Boot & errors**
- [ ] When I launch the app, then the window opens immediately on a loading screen and switches to the app once the backend is healthy, landing on Models.
- [ ] When the **backend fails to start** (port in use, crash, timeout), then the app shows a clear error with the reason (code + log path) and Retry/Quit — **not** a perpetual spinner.
- [ ] When the backend dies **after** load, then API calls fail per-screen with a visible error.

**Offline & persistence**
- [ ] When I launch **offline**, then my downloaded models still list and work, the catalog shows from the bundled snapshot, and Hugging Face search reports no connection.
- [ ] When I quit and relaunch, then my conversations, knowledge bases, downloaded models, and settings all persist.
- [ ] When the catalog refreshes on restart, then my downloaded and in-progress models are never altered (only remote suggestions reconcile, with stable IDs).
- [ ] When I **force-kill** the app and relaunch, then it recovers (stale DB locks pruned) and interrupted download/KB jobs are marked failed and cleaned up.
- [ ] When I close the window on **macOS**, then the app keeps running; on **Windows/Linux**, closing the last window quits and stops the backend.
- [ ] When I use Help → **"Clear All Data"** and confirm, then the backend stops, the data directory is deleted, and the app quits.

**Updates & first run**
- [ ] When I run a **packaged** build and a newer release is published, then a banner shows "downloading…", then "ready — restart to install", and it installs on click or next quit.
- [ ] When a release is still a **draft**, then my installed build is **not** offered that update.
- [ ] When I do a **fresh install**, then the Welcome dialog shows once, the catalog seeds instantly from the bundled snapshot (then refreshes in the background), and the machine readout renders (even if hardware profiling falls back).
- [ ] When the app quits, then the backend and its inference child processes are stopped (none left orphaned).

---

### How to record a run

Per release candidate, note: build version, OS + hardware, who ran it, date, and
any **FAIL** with a linked issue. For a FAIL, grab both log files and the `fe-…`
request id of the failing action — locations and the tracing recipe are in
[docs/logging.md](docs/logging.md). Platform coverage (which OS/GPU each artifact
was tested on) is tracked in `docs/dev/release-qa-checklist.md`. Scenarios marked
*(see #136)* are known **P2** UX defects (not release-blocking), tracked in #136;
the release-blocking defects from the bug bash (#133) are fixed (PR #135).
