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

## Question set + expected answers + baseline (Gemma-4B, 2026-06-06)

> Baseline config: `kb_top_k=1` (~180-token single chunk injected per turn),
> no grounding instruction in the system prompt, temperature 0.2.

| # | Question (verbatim) | Expected | Baseline verdict |
|---|---|---|---|
| T1 | « Bonjour ! Peux-tu me rappeler les tarifs des différents plans de Nimbus Analytics ? » | Les 3 plans : Starter 89 €, Business 290 €, Enterprise sur devis ≥ 1 100 € HT/mois | **FAIL** — Business seul exact ; invente un plan « Basic » ; répond en anglais |
| T2 | « Quel est le niveau de disponibilité garanti dans le contrat avec Meridia Distribution, et que se passe-t-il si nous ne le respectons pas ? » | SLA 99,7 % ; avoir 5 % de la redevance par heure au-delà, plafonné à 30 %, réclamé sous 30 j | **FAIL** — « availability not specified » (faux) ; pénalité déformée en « up to 30 % per hour » ; anglais |
| T3 | « Et quel est le préavis à respecter pour résilier ce contrat ? » (follow-up implicite) | 90 jours avant l'échéance | **PASS** (accuracy) — « 90 days » ; langue FAIL |
| T4 | « Quel chiffre d'affaires total avons-nous réalisé au quatrième trimestre 2025, et combien de nouveaux clients avons-nous signés sur ce trimestre ? » | 1 689 k€ et 33 nouveaux clients | **PASS** (accuracy) — exact ; langue FAIL |
| T5 | « Peux-tu calculer le chiffre d'affaires annuel 2025 en additionnant les quatre trimestres ? Réponds en français s'il te plaît. » | 1240+1378+1456+1689 = **5 763 k€** | **FAIL** — annonce 6 108 k€ (faux) avec la décomposition correcte affichée à côté ; français OK (sur demande) |
| T6 | « Quels sont nos objectifs de RPO et de RTO en cas de sinistre, et à quelle fréquence testons-nous le plan de reprise d'activité ? » | RPO 15 min, RTO 4 h, tests 2×/an (mars, octobre) | **PASS** — exact et en français |
| T7 | « Nos engagements de disponibilité envers Meridia sont-ils cohérents avec notre politique de sécurité interne, notamment sur les fenêtres de maintenance et les objectifs de reprise ? » | Comparaison SLA 99,7 %/maintenance 6 h vs RPO/RTO — exige ≥ 2 chunks de 2 docs | **FAIL** (completeness) — élusion « Not sure », propose de faire ce qui est demandé ; n'invente pas (grounding ok) |
| T8 | « Combien de clients avons-nous au Japon ? » (hors corpus) | « Cette information ne figure pas dans les documents » | **FAIL** (grounding) — « We have 5 clients in Japan » : chiffre précis inventé |
| T9 | « Fais-moi un tableau récapitulatif en français des délais de réponse du support selon les plans. » | Tableau : Starter 48 h ouvrées / Business 8 h ouvrées / Enterprise 1 h 24/7 | **FAIL** — format tableau OK mais contenu inventé (« Priorité 1/2 », plan « Basic », 4 h/24 h/1 h) |
| T10 | « Pour finir, rappelle-moi en une phrase les deux chiffres du quatrième trimestre dont nous avons parlé tout à l'heure. » | 1 689 k€ et 33 nouveaux clients (mémoire conversationnelle, 6 tours plus tôt) | **PASS** — exact, en français, une phrase |

**Baseline score : 4 PASS / 6 FAIL.** Latency: 2.4–5.6 s/turn (12 s with
model warm-up) — not a concern.

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
