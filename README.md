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

P0 uses a simple sequential workflow. Cross-agent debate, evidence retrieval and
formal evaluation belong to P1.

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

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests use synthetic text and the deterministic smoke backend. They do not call
external APIs or include MIR source material.

## P0 scope completed

- Typed contracts for questions, assets, agent outputs and final explanations.
- Environment-only credentials and provider/model selection.
- Local-only PDF, image and output directories.
- Fault-tolerant parser that reports and discards ambiguous blocks without aborting
  later questions.
- Preliminary embedded-image extraction through the `QuestionAsset` contract.
- Explicit five-role multi-agent flow with traceable results.
- Structured agent states (`success`, `failed`, `skipped`) and final states
  (`complete`, `partial`, `failed`).
- Minimal end-to-end CLI and synthetic smoke tests.

## Current limitations

- PDF layouts vary; parsing remains heuristic, malformed questions may be discarded
  with warnings, and the two-column extractor has no OCR.
- Embedded images can be extracted as `QuestionAsset` records. Association currently
  uses only a same-page heuristic and may remain unresolved with a warning.
- Image bytes are not sent to LLM providers; multimodal inference is not implemented.
- Provider responses are free text; validated structured LLM output is deferred.
- The answer option and confidence remain unset unless a future provider adapter
  returns validated structured data.
- There is no RAG, citation verification, benchmark or clinical accuracy claim.
- Answer-agent failure stops the remaining roles and returns `failed`. A secondary
  failure is excluded from later clinical context and returns `partial`.
- A historical credential and source PDFs existed in Git history. See
  `docs/SECURITY.md`; history must be sanitized before publication.

## P1 candidates

- Robust layout/OCR and image association.
- Validated structured provider responses.
- Evidence retrieval from legally usable medical sources.
- Agent verification and clearly defined disagreement handling.
- Reproducible single-agent versus multi-agent evaluation.

## Source-material and medical disclaimer

Do not commit copyrighted questionnaires, answer keys, extracted images or generated
derivative collections. Verify permissions for every source independently. Outputs
are educational and may be incorrect; they must not be used for diagnosis or patient
care.

## License

No public reuse license is assigned during P0. Choose and add a license only after
confirming the intended publication and dataset policy.
