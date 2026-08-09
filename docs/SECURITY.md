# Security and source-material policy

## Exposed historical credential

A credential-like OpenAI value was committed in the early Git history. It must
be considered compromised and revoked or rotated at the provider. Removing the
file from the current tree does not remove it from earlier commits.

Before any publication, rewrite the private repository history with an approved
history-rewriting tool, verify the resulting object database, and force-push only
after coordinating with every clone owner. History rewriting is intentionally not
performed automatically during P0 because it is destructive.

## Local secrets

Copy `.env.example` to `.env` and store real credentials only in `.env` or in a
secret manager. `.env` files are ignored. Logs must not include credentials or
complete provider error payloads.

## MIR source material

PDF questionnaires, extracted images, answer keys and generated outputs are local
inputs, not distributable project assets. Their copyright and redistribution terms
must be verified independently. Keep them under ignored directories:

- `data/input/` for PDFs
- `data/images/` for extracted images
- `outputs/` for generated questions and explanations

Only synthetic or explicitly redistributable fixtures may be committed to tests.
