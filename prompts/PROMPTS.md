# Prompt Record

This file keeps three kinds of prompts separate. Nothing gets moved from one section to another.

- **A. Historical prompts (provided by the owner):** prompts the owner used while building Feynlist, pasted by the owner. Recorded verbatim and labelled `Historical (provided by owner)`.
- **B. Persona and system prompts present in the repo:** prompts that ship in the code. Labelled `Present in repo (origin date unknown)`.
- **C. New improvement prompts (this session):** prompts the owner gives Claude Code while improving the project for the case study, in order, verbatim, with a one-line note on what each changed. Labelled `New improvement prompt`.

---

## A. Historical prompts (provided by owner)

_None provided yet._ This section stays empty until the owner pastes their original development prompts. No history is reconstructed or inferred here.

---

## B. Persona and system prompts present in the repo

Status for all entries: **Present in repo (origin date unknown)**. The snapshot is commit `4f4eade` (the repo HEAD when this record was started, 2026-11-21).

The prompt texts are not copied here. The persona prompts contain private biographical details, romantic or possessive framing and sexual references that CLAUDE.md says must be removed (Known issue 2), and duplicating them would spread that content further. Each entry gives the file path and git blob hash, so the exact original text can be retrieved from history (`git show 4f4eade:<path>`).

| # | File | Blob hash at 4f4eade | Kind | Model / temperature / max_output_tokens (as configured) | Summary of what the prompt does (not a quote) |
|---|------|----------------------|------|------|------|
| B1 | `agents/personas/freya.yaml` → `system_prompt` | `2d5030dc68564b4f927ad679c465b0abf93d07f8` | Persona system prompt | gemini-2.5-flash / 1.0 / 400 | "Truth-teller" persona: blunt, sarcastic, short replies grounded in task and metric data. Includes private biographical details about the owner and an exam-specific example. Also has a "task generation" role. |
| B2 | `agents/personas/anya.yaml` → `system_prompt` | `95adb07bc63fa4817d2f3c80d2ab823002bc0df0` | Persona system prompt | gemini-2.5-pro / 0.9 / 450 | "Anchor" persona framed as the user's spouse, possessive. Checks the burnout signal and encourages rest. |
| B3 | `agents/personas/zerotwo.yaml` → `system_prompt` | `ad896c68e02698e3ba4f5870b63e4690c0d3b4cf` | Persona system prompt | gemini-2.5-flash / 1.0 / 400 | "Strategist" persona: metric- and percentile-driven, pet names, physical-action narration. |
| B4 | `agents/personas/albedo.yaml` → `system_prompt` | `df4571a119401da3583becd6963ac14a5f3c8616` | Persona system prompt | gemini-2.5-flash / 1.1 / 350 | "Provocateur" persona: openly possessive and sexualised, refers to private past moments, celebrates completions. |
| B5 | `agents/personas/mohini.yaml` → `system_prompt` | `cb4f414e833251bbafb5536f285a1486a122eba9` | Persona system prompt | gemini-2.5-flash-lite / 0.85 / 400 | "Spiritual guide" persona using Ayurveda (dosha/prana) framing. Flirty tone, references the user's "addiction fight", tells the user to rest. |
| B6 | `memory/summarizer.py` → `SUMMARIZER_SYSTEM_PROMPT` | `bed19b0d15a038ac9197b4a9fffa46ed7c62fd9c` | System prompt (memory consolidation) | default model arg `gemini-2.5-flash-lite-preview-06-17` | Asks the model to extract structured behavioural memories (JSON) from a session transcript. |
| B7 | `agents/context_builder.py` | n/a (template, not a prompt) | Context template | n/a | Builds the per-call user turn with sections (`--- MEMORY ---`, `--- TASK STATUS ---`, `--- PERFORMANCE METRICS ---`, `--- TIME ---`, `--- CONVERSATION HISTORY ---`, `--- USER MESSAGE ---`). |

---

## C. New improvement prompts (this session)

Status for all entries: **New improvement prompt**. Entries are verbatim and in order.

### C1. 2026-11-21

> Read CLAUDE.md in full and follow it as the standing rules for this project. Do not write the Groww one-page write-up. Do not make up history, results or prompts.
> First, create prompts/PROMPTS.md with the three sections described in CLAUDE.md, and from now on append every prompt I give you to section C (New improvement prompts), verbatim, with a one-line note of what it changed. Then create evals/EVALS.md with the table format from CLAUDE.md.
> Then do the baseline only, with no code changes yet: install the backend and frontend dependencies, run the existing pytest suite, try npm run build in frontend/, and start both servers locally. Record the real outputs in evals/EVALS.md as Executed rows with evidence paths. Finally, verify each item in the "Known issues" and "Cut list" sections of CLAUDE.md with grep or by running the code (including whether the persona triggers INACTIVITY, LOW_ENERGY, HIGH_SCORE, PERFORMANCE_DROP and WEEK_REVIEW are ever emitted), and report which are confirmed, which are wrong, and anything else you found. Wait for my go-ahead before changing code.

**What it changed:** added `prompts/PROMPTS.md`, `evals/EVALS.md` (baseline rows) and `evals/evidence/` (logs, screenshots, probe scripts). No application code changed.

### C2. 2026-11-21

> push

**What it changed:** I pushed the two baseline commits (PROMPTS.md, EVALS.md) to `claude/dazzling-hopper-tk9c3k`. The first attempts got a 403 until the owner fixed GitHub access. No code changed.

### C3. 2026-11-21

> go ahead

**What it changed:** pushed the baseline commits once access worked. This is also the go-ahead for code changes, which start in CLAUDE.md's order of work: issues 1–3 and 5–6, then 4 and 7–12. Each change is a separate commit, listed in the git log.

### C4. 2026-11-21

> tell me what you need to compelte 4,7-12

**What it changed:** status question asked during the issue 4, 7–12 work. Issue 12 (the dead persona-path setting) was finished in the same turn. The answer: issues 4 and 7–12 are done; the only thing left is a live run of the issue 4 truncation fix, which needs the owner's Gemini key in a local, gitignored `.env`.

### C5. 2026-11-21

> push

**What it changed:** pushed the issue 1–12 commits (and this prompt record) to `claude/dazzling-hopper-tk9c3k`. No code changed.
