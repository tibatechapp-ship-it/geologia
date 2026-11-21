# Ali Algomori routing evaluation

## Purpose

A curated regression suite checks deterministic intent routing across Arabic, English, Russian, and Chinese. It protects the known lexicon from regressions and verifies that requests without geoscience signals abstain instead of being routed to GIS by default.

## Scope

- 24 positive examples: six supported domains in each of four languages.
- Four negative examples: one per language.
- Every positive case must return exactly its expected domain set and visible routing evidence.
- Every negative case must return no domains and request clarification.

## Current evaluation

The suite is intentionally authored around supported terminology. It is **not** an independent, statistically representative language benchmark, does not measure scientific correctness, and cannot establish general multilingual understanding. Future evaluation should add reviewed real-world requests, ambiguous and adversarial wording, held-out terminology, and domain-expert adjudication.

No model training or scientific engine execution is involved.
