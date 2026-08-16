# MIR Multi-Agent Study Pipeline

Experimental Python pipeline for extracting MIR-style study questions from local
PDF questionnaires and producing an explanation through specialized LLM roles.
It is an educational prototype, not a clinical decision-support system.

## Objective

For each parsed question, the project preserves the original stem, 2–5 options,
source metadata and optional image references. Five explicit roles then contribute:

1. **Answer agent** — proposes the best answer and core justification.
2. **Pharmacology agent** — discusses relevant drugs and mechanisms.
3. **Clinical agent** — explains clinical reasoning and distractors.
4. **Terminology agent** — defines the necessary medical concepts.
5. **Mnemonic agent** — builds a visual analogy from the previous analyses.

P0 preserves a legacy sequential smoke workflow. P1 adds structured one-question
analysis with an independent reviewer; evidence retrieval and formal evaluation are
still out of scope.

## Architecture

```text
Local PDF
  -> page/two-column extraction
  -> fault-tolerant parser + extraction report
  -> preliminary embedded-image assets
  -> MirQuestion contract
  -> answer -> pharmacology -> clinical -> terminology
  -> mnemonic (receives prior analyses)
  -> FinalExplanation contract
  -> JSON output
```

P1 one-question analysis:

```text
Validated MirQuestion + trusted image bytes (when required)
  -> QuestionPackage input gate
  -> independent AnswerResolver + IndependentReviewer
  -> clinical / pharmacology / terminology / scales / option analysis
  -> structural agreement check
  -> adjudicator only on disagreement
  -> 3-7 high-yield points
  -> absurd visual mnemonic using accepted facts only
  -> FinalStudyExplanation JSON
```

Key directories:

- `src/mir_multiagent/`: contracts, ingestion, providers, agents and orchestration.
- `src/mir_multiagent/resources/prompts.json`: packaged role prompts, without credentials.
- `data/input/`: ignored local PDFs.
- `data/images/`: ignored extracted or associated images.
- `outputs/`: ignored generated results.
- `tests/`: synthetic smoke tests only.
- `docs/SECURITY.md`: secret and source-material policy.

## Installation

Python 3.10 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

For Groq:

```bash
python -m pip install -e '.[groq,dev]'
```

For LM Studio or another OpenAI-compatible local server:

```bash
python -m pip install -e '.[local,dev]'
```

## Secure configuration

```bash
cp .env.example .env
```

Select one backend in `.env`:

```dotenv
MIR_LLM_PROVIDER=groq
MIR_LLM_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=your-local-secret
```

or:

```dotenv
MIR_LLM_PROVIDER=openai_compatible
MIR_LLM_BASE_URL=http://localhost:1234/v1
MIR_LLM_API_KEY=local-development-only
MIR_LLM_MODEL=your-loaded-model
```

Each role can override the default through `MIR_ANSWER_MODEL`,
`MIR_PHARMACOLOGY_MODEL`, `MIR_CLINICAL_MODEL`, `MIR_TERMINOLOGY_MODEL` and
`MIR_MNEMONIC_MODEL`. Never commit `.env`.

The default `mock` backend exists only to verify plumbing. Its output is visibly
marked `SMOKE_TEST_ONLY` and is not a medical response.

## Run

Place a legally usable local PDF under `data/input/`, then run:

```bash
python -m mir_multiagent data/input/questionnaire.pdf --question-index 0
```

Write the result to the ignored output directory:

```bash
python -m mir_multiagent data/input/questionnaire.pdf \
  --question-index 0 \
  --output outputs/question-1.json
```

### Analyze one question into structured study output

Select by original MIR number rather than parser index:

```bash
MIR_LLM_PROVIDER=mock python -m mir_multiagent analyze-question \
  data/input/exam.pdf \
  --question-number 28 \
  --output outputs/question-28.json
```

For separate image sheets:

```bash
MIR_LLM_PROVIDER=mock python -m mir_multiagent analyze-question \
  data/input/questions.pdf \
  --images-pdf data/input/images.pdf \
  --question-number 8 \
  --output outputs/question-8.json
```

The image input gate reads the actual asset bytes. A required missing image returns
`missing_required_image`; low-confidence association returns `needs_asset_review`;
and a text-only provider returns `model_does_not_support_images`. No silent
text-only fallback is performed.

An optional local official key may be supplied:

```json
{
  "28": {"official_answer": "3", "annulled": false}
}
```

```bash
python -m mir_multiagent analyze-question data/input/exam.pdf \
  --question-number 28 --official-key answers.json
```

Predicted and official answers remain separate. A model may flag a question as
potentially invalid, but only supplied local official evidence can mark it annulled.

### Validate a complete MIR exam without an LLM

General PDFs do not require a fixed number of questions. When the input is known to
be a complete MIR exam, run an explicit structural audit:

```bash
python -m mir_multiagent validate-extraction \
  data/input/exam.pdf \
  --expected-questions 210 \
  --output outputs/extraction-audit.json
```

This command never constructs an LLM provider or runs an agent. It reports recovered,
missing, duplicate, unexpected and unnumbered questions, plus image extraction and
association statistics. `--debug-extraction` prints only short previews, fingerprints
and provenance for ambiguous blocks; it does not print the complete exam.

If the questionnaire and its labelled image sheets are separate PDFs, pass both:

```bash
python -m mir_multiagent validate-extraction \
  data/input/questions.pdf \
  --images-pdf data/input/images.pdf \
  --expected-questions 210
```

Only the first PDF is parsed as questions. Assets from the second PDF are extracted
from explicit `IMAGEN N` labels and named `<images-pdf>-imagen-N.png`; labels and
questions remain unassociated unless the questionnaire provides structural evidence.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests use synthetic text and the deterministic smoke backend. They do not call
external APIs or include MIR source material.

## Extraction and analysis scope completed

- Typed contracts for questions, assets, agent outputs and final explanations.
- Environment-only credentials and provider/model selection.
- Local-only PDF, image and output directories.
- Fault-tolerant parser that reports and discards ambiguous blocks without aborting
  later questions.
- Preliminary embedded-image extraction through the `QuestionAsset` contract.
- Explicit complete-exam reconciliation using original source question numbers.
- Cross-column and conservative cross-page reconstruction with page provenance.
- Multimodal `QuestionPackage` with real image bytes and conservative asset gates.
- Typed resolver, per-option analysis, clinical, pharmacology, terminology,
  scales/formulas, high-yield and mnemonic outputs.
- Independent pre-comparison reviewer and conditional disagreement adjudication.
- Structured one-question `analyze-question` CLI with a deterministic offline mock.
- Explicit five-role multi-agent flow with traceable results.
- Structured agent states (`success`, `failed`, `skipped`) and final states
  (`complete`, `partial`, `failed`).
- Minimal end-to-end CLI and synthetic smoke tests.

## Current limitations

- PDF layouts vary; parsing remains heuristic, malformed questions may be discarded
  with warnings, and the two-column extractor has no OCR.
- Embedded images can be extracted as `QuestionAsset` records. Association currently
  uses explicit referenced image numbers when present. Unnumbered references may use
  a unique same-page asset at low confidence or remain unresolved with a warning.
- Vision support depends on the configured provider and model. Correct asset
  association must be established before image analysis.
- External model JSON is validated after generation; malformed output produces an
  explicit failed or partial result rather than guessed fields.
- P1 analyzes one question at a time; full-exam batch execution is intentionally absent.
- There is no RAG, citation verification, benchmark or clinical accuracy claim.
- Answer-agent failure stops the remaining roles and returns `failed`. A secondary
  failure is excluded from later clinical context and returns `partial`.
- A historical credential and source PDFs existed in Git history. See
  `docs/SECURITY.md`; history must be sanitized before publication.

## Future candidates

- Robust layout/OCR and additional image-association formats.
- Evidence retrieval from legally usable medical sources.
- Reproducible single-agent versus multi-agent evaluation.

## Source-material and medical disclaimer

Do not commit copyrighted questionnaires, answer keys, extracted images or generated
derivative collections. Verify permissions for every source independently. This is
AI-assisted MIR question analysis for structured education, not an official answer
key or clinically validated solver. Outputs may be incorrect and must not be used for
diagnosis or patient care. Independent model agreement is not proof of correctness.

## License

No public reuse license is assigned during P0. Choose and add a license only after
confirming the intended publication and dataset policy.
