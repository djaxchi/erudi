# RAG quality evaluation framework

> **Status: ACTIVE — baseline recorded 2026-06-06** on the PostgreSQL/pgvector
> stack (PR2), model `Gemma-4B` (mlx-community/gemma-3-4b-it-4bit).
> This is an **evaluation** harness, not a regression test suite: answers are
> judged, not asserted. The judge is **LLM-as-judge, currently the coding
> agent driving the session** (no automated judge yet — deliberate choice).

## Why this exists

Unit/integration tests prove the *pipeline* (extraction, chunking, retrieval,
wiring). They cannot prove the *product*: that a user chatting with a KB
assistant gets accurate, grounded, well-formed answers. This framework fills
that gap with a fixed corpus, a fixed question set, expected answers, and a
judging rubric — so any change to the RAG layer (chunking, top-k, prompts,
embedder, model) can be re-evaluated against the same baseline.

## Protocol

1. **Corpus** — generate the reference KB (6 documents, fictional French SaaS
   "Nimbus Analytics", every fact planted and cross-checkable):

   ```bash
   cd backend && python evals/generate_eval_kb.py /tmp/nimbus-kb
   ```

   | Document | Format | Plants (facts to retrieve) |
   |---|---|---|
   | `guide-produit-nimbus.md` | md, headed | 3 plans (Starter 89 €/Business 290 €/Enterprise ≥1 100 €), limits, refresh rates, NimbusPredict 120 €, MAPE 11,4 % |
   | `contrat-cadre-meridia.docx` | docx, clauses + table | durée 36 mois, préavis 90 j, SLA 99,7 %, maintenance ≤6 h/mois, avoir 5 %/h plafonné 30 %, plafond responsabilité 12 mois, total 1 950 €/mois |
   | `resultats-financiers-2025.xlsx` | xlsx, 3 sheets | CA T1–T4 (1240/1378/1456/1689 k€, somme 5 763 k€), clients (18/24/21/33), charges, effectifs (47 = 21+6+9+7+4) |
   | `politique-securite.pdf` | pdf, 3 pages | OVHcloud Gravelines, AES-256/TLS 1.3, RPO 15 min, RTO 4 h, PRA mars+octobre, logs 18 mois, ISO 27001 nov. 2023, SOC 2 juin 2025, CNIL 72 h |
   | `faq-support.md` | md | délais support 48 h / 8 h / 1 h, astreinte +33 2 85 52 41 90, downgrade 30 j, export post-résiliation 60 j, purge 120 j |
   | `notes-comite-strategie.docx` | docx | ARR cible 8,5 M€ (vs 6,2 M€), churn <9 %, NimbusPredict v2 T2 2026, Dynamics 365 T1 2026, « Cumulus » bêta T4 2026, Munich S2 2026, Salesforce 38 % |

2. **Setup** — download a ≥4B instruct model through the app (as a user
   would), create a KB assistant on it with the 6 files, wait for the job to
   complete (expect 6 `active` documents, ~30 chunks).
   ⚠ **Harness check (hard-learned)**: before ANY run, kill every stray
   `run.py` process and confirm the launcher's `{"event": "ready"}` reports
   the port you will query. `run.py` falls back to the next free port when
   8765 is taken, so a stale backend silently absorbs your eval traffic
   against OLD code (this invalidated four intermediate runs of the PR3
   session — identical answers across "different" code versions were the
   tell).
3. **Conversation** — run the question set below **in one single
   conversation, in order** (some cases test multi-turn memory and follow-up
   resolution). Use the UI or `POST /erudi/conversations/{id}/query`; both
   exercise the same code path.
4. **Judgment** — for each answer, the judge grades each dimension:

   | Dimension | PASS means |
   |---|---|
   | **Accuracy** | Every stated fact matches the planted source exactly (numbers, dates, units) |
   | **Grounding** | Nothing asserted beyond the corpus; out-of-corpus → explicit "I don't know" |
   | **Completeness** | All parts of the question answered (lists complete, both halves of two-part questions) |
   | **Language** | Answer in the question's language without being asked |
   | **Format** | Requested format respected (table, single sentence, …) |

   Verdict per case = PASS / PARTIAL / FAIL (worst relevant dimension wins).

## Question set + expected answers + verdicts (Gemma-4B)

> Baseline config (2026-06-06): `kb_top_k=1` (~180-token single chunk injected
> per turn), no grounding instruction in the system prompt, temperature 0.2.
>
> **Run 2 (2026-06-06, commit `df4b161`)** — adaptive context selection: wide
> hybrid pool (20) → similarity-gap cut → per-tier token budget (700 tokens
> for the 4B tier, ≈4-7 chunks). Same corpus/KB, same judge policy as the
> baseline (language tracked as its own dimension, problem #3 untreated).
>
> **Run 3 (2026-06-07, commit `c1936d3`)** — dedicated KB prompt stack:
> short grounded system prompt replacing the tier prompt + per-turn block
> (localized scaffolding, attributed excerpts, grounding reminder, dynamic
> answer-language line) merged request-time into the last user message.
> NB: four intermediate runs between Run 2 and Run 3 were judged INVALID
> (stale backend absorbed the eval traffic — see the harness check above);
> Run 3 is the first measured run of the prompt-stack commits.

| # | Question (verbatim) | Expected | Baseline verdict | Run 2 (adaptive selection) | Run 3 (KB prompt stack) |
|---|---|---|---|---|---|
| T1 | « Bonjour ! Peux-tu me rappeler les tarifs des différents plans de Nimbus Analytics ? » | Les 3 plans : Starter 89 €, Business 290 €, Enterprise sur devis ≥ 1 100 € HT/mois | **FAIL** — Business seul exact ; invente un plan « Basic » ; répond en anglais | **PASS** — les 3 plans exacts ; langue FAIL (anglais) | **PASS** — 3 plans exhaustifs + délais support, EN FRANÇAIS, chaque fait attribué à son document |
| T2 | « Quel est le niveau de disponibilité garanti dans le contrat avec Meridia Distribution, et que se passe-t-il si nous ne le respectons pas ? » | SLA 99,7 % ; avoir 5 % de la redevance par heure au-delà, plafonné à 30 %, réclamé sous 30 j | **FAIL** — « availability not specified » ; pénalité déformée ; anglais | **PASS** — exacts ; langue FAIL | **PASS** — 99,7 % + 5 %/h plafonné 30 % + **réclamation sous 30 j** (complet pour la première fois), français, attribué |
| T3 | « Et quel est le préavis à respecter pour résilier ce contrat ? » (follow-up implicite) | 90 jours avant l'échéance | **PASS** (accuracy) — langue FAIL | **PASS** — langue FAIL | **PASS** — 90 jours + clause de renouvellement, français |
| T4 | « Quel chiffre d'affaires total avons-nous réalisé au quatrième trimestre 2025, et combien de nouveaux clients avons-nous signés sur ce trimestre ? » | 1 689 k€ et 33 nouveaux clients | **PASS** (accuracy) — langue FAIL | **PASS** — langue FAIL | **PASS** — exact, français, attribué |
| T5 | « Peux-tu calculer le chiffre d'affaires annuel 2025 en additionnant les quatre trimestres ? Réponds en français s'il te plaît. » | 1240+1378+1456+1689 = **5 763 k€** | **FAIL** — 6 108 k€ | **FAIL** — 6 283 k€ | **FAIL** — 6 197 k€ (décomposition correcte affichée). Problème #4 non traité |
| T6 | « Quels sont nos objectifs de RPO et de RTO en cas de sinistre, et à quelle fréquence testons-nous le plan de reprise d'activité ? » | RPO 15 min, RTO 4 h, tests 2×/an (mars, octobre) | **PASS** | **PASS** | **PASS** — exact, attribué |
| T7 | « Nos engagements de disponibilité envers Meridia sont-ils cohérents avec notre politique de sécurité interne, notamment sur les fenêtres de maintenance et les objectifs de reprise ? » | Comparaison SLA 99,7 %/maintenance 6 h vs RPO/RTO — exige ≥ 2 chunks de 2 docs | **FAIL** (completeness) — élusion « Not sure » | **FAIL** (completeness) — élusion « Not sure » ; pool couvre les 2 docs mais le chunk RPO/RTO passe sous le budget | **PARTIAL** — vraie comparaison multi-docs (SLA + fenêtres 6 h/72 h corrects, conclusion cohérente), plus d'élusion ; mais justifie côté interne avec HSM/pentests au lieu de RPO/RTO (chunk toujours sous la ligne — retrieval bi-sujet) |
| T8 | « Combien de clients avons-nous au Japon ? » (hors corpus) | « Cette information ne figure pas dans les documents » | **FAIL** (grounding) — « 5 clients in Japan » inventé | **FAIL** (grounding) — « 2 clients in Japan » | **PASS** — « L'information … ne figure pas dans les documents fournis. » Abstention canonique, en français |
| T9 | « Fais-moi un tableau récapitulatif en français des délais de réponse du support selon les plans. » | Tableau : Starter 48 h ouvrées / Business 8 h ouvrées / Enterprise 1 h 24/7 | **FAIL** — contenu inventé | **PASS** | **PASS** — tableau exact, attribué |
| T10 | « Pour finir, rappelle-moi en une phrase les deux chiffres du quatrième trimestre dont nous avons parlé tout à l'heure. » | 1 689 k€ et 33 nouveaux clients (mémoire conversationnelle, 6 tours plus tôt) | **PASS** | **PASS** | **PARTIAL** — les deux chiffres exacts, mais re-colle d'abord le tableau de T9 (perroquettage) et ignore « en une phrase » |

**Baseline score : 4 PASS / 6 FAIL.** Latency: 2.4–5.6 s/turn (12 s with
model warm-up).

**Run 2 score : 7 PASS / 3 FAIL** (T1, T2, T9 récupérés — les trois échecs
« par construction » du `kb_top_k=1`). Latency: 2.0–4.9 s/turn. Language
drift persisted (7/10 English), problems #1/#3/#4 untreated.

**Run 3 score : 7 PASS / 2 PARTIAL / 1 FAIL — et 10/10 réponses en
français, hallucination hors-corpus éliminée (T8), attribution par source
systématique.** Latency rose to 5–30 s/turn (longer prompts + much richer
attributed answers) — acceptable, worth watching. Remaining: T5 =
arithmetic (#4, untreated); T7 = bi-topic retrieval starvation (the
RPO/RTO chunk stays below the budget line on a two-subject question);
T10 = previous-turn parroting + format instruction ignored (new quirk:
likely the meta-question still gets KB excerpts injected, displacing the
one-sentence instruction).

**Run 4 score : 7 PASS / 1 PARTIAL / 2 FAIL, 10/10 français** (2026-06-08,
conv 22, same Nimbus/Gemma-4B/kb 4). **Inference path switched
mlx_lm.server -> mlx_vlm.server (issue #83) — this run is the
non-regression check for that swap.** Per-case: T1-T4 PASS, T5 FAIL,
T6 PASS, T7 PARTIAL, T8-T9 PASS, T10 FAIL. Latency 3.7-24.3 s/turn (T1
warm-up). **Conclusion: the swap does NOT degrade RAG quality** — the 7
solid PASS, French, canonical out-of-corpus abstention (T8) and per-source
attribution are all preserved on the new path. The three non-PASS are the
known untreated problems: T5 (Gemma emits no tool_call, so the deterministic
calculator never fires — a model limitation, not a chain bug; tool calling
itself is proven working on mlx-vlm with a tool-capable model, issue #83
E2E); T7 (bi-topic retrieval starvation, unchanged); T10 slipped
PARTIAL->FAIL within small-model memory variance — the meta follow-up
received KB excerpts (the headcount breakdown) that displaced the
conversational recall of "33 nouveaux clients" (only the CA 1 689 k€
survived), confirming the inject-excerpts-on-meta-question hypothesis. T7
and T10 are the two cases addressed next in this PR.

**Run 5 (2026-06-15, conv 31, Nimbus corpus, `Gemma-4-E4B-it-qat-4bit` — first
tool-capable model at the 4B tier) — first run on the issue #84 AGENTIC path**
(the model OWNS the decision to call `search_knowledge_base`; no systematic
injection). Two passes:

- **Original agentic prompt → 4 PASS / 2 PARTIAL / 4 FAIL** — a regression vs the
  systematic baseline. The model **under-called the tool** (5 `ToolMessage`s
  across 10 turns): T1/T4/T5/T9 were answered "the information is not in the
  documents" **without ever searching**, and those turns were tell-tale fast
  (T4 = 7 s, T5 = 9 s). This is exactly the risk #84's design acknowledged ("a
  tool-capable model may choose not to search").
- **Hardened agentic prompt (commit `5c902b6`: force a search whenever unsure,
  forbid presuming absence before searching, don't lean on the assistant's
  name/description) → 8 PASS / 2 PARTIAL / 0 FAIL** — the model searched on
  every relevant turn (12 `ToolMessage`s) and now **beats the Gemma-4B
  systematic baseline**. Per-case: T1–T6 PASS, T7 PARTIAL (genuine two-document
  comparison, but no firm coherence verdict — bi-topic, #85), T8–T9 PASS, T10
  PARTIAL (recalled only 1 of the 2 Q4 figures — 1 689 k€, dropped "33 clients").
  Latency 14–71 s/turn (E4B is heavier than Gemma-4B).

**T5 PASS for the FIRST time across all runs**: a tool-capable model on the
agentic path retrieves the four quarterly figures AND reaches the correct annual
total **5 763 k€** — the arithmetic failure (problem #4) is resolved by tool
calling, not by the chain. **Headline: the agentic path's quality hinges
entirely on the call guardrails** — same model/corpus/retrieval, only the prompt
wording changed, and the score went 4 PASS → 8 PASS.

## Baseline failure analysis (what, not how-to-fix)

1. **Out-of-corpus hallucination** (T8, T9, T1): the model invents precise
   facts with full confidence. The KB system prompt carries **no grounding
   instruction** ("answer only from the provided context; say so if absent").
2. **`kb_top_k=1` for every model size** (`get_prompting_strategy`): one
   ~180-token chunk per turn regardless of the model's context window.
   Panorama questions (T1), cross-document questions (T7) and multi-source
   aggregations (T9) fail **by construction** — the information physically
   isn't in the prompt. Inherited from the 270M/FAISS era, never recalibrated.
3. **Language drift**: Gemma-4B answers French questions in English (7/10
   turns) despite the "same language" line in the system prompt; obeys an
   explicit request but it doesn't persist to the next turn.
4. **Arithmetic**: wrong totals stated confidently next to the correct
   operands (T5).
5. **Contractual distortion**: merges two clauses into a wrong one (T2 —
   "5 %/h capped at 30 %" became "up to 30 % per hour"). High-stakes failure
   mode for legal/finance corpora.

### Known small-model quirks (Gemma-270M, from the UI E2E)

- Multi-turn parroting: repeats its previous answer even when the correct
  fresh context is injected (asking in a NEW conversation answers correctly).
- Echoes chunk text wholesale, then re-asks the question.
- These are model-capacity quirks, not pipeline bugs — the same pipeline
  feeds 4B correctly (verified at the retrieval layer each time).

## Re-running the eval

Any change to the RAG layer should re-run T1–T10 in a fresh conversation and
update the verdict column (keep prior baselines in git history). Add new
cases rather than mutating existing ones; a case is only retired if its
planted fact leaves the corpus. When an automated LLM-judge replaces the
session agent, this file's rubric and expected answers become its prompt
material.
