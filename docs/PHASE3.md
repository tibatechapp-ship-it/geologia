# Phase 3 — Ali Algomori deterministic agent and data readiness

**Ali Algomori (علي الگوموري)** is the GEOLOGIA chief geoscience agent identity. The current core is a lightweight, local, deterministic rules engine—not a trained neural model, not an LLM, and not a claim of human-like autonomous reasoning.

## Implemented behavior

- Normalizes Arabic and English requests with Unicode normalization, case folding, punctuation normalization, and whole-phrase boundaries.
- Routes requests to one or more specialist domains using a versioned keyword catalog.
- Records the matched terms as routing evidence for every domain.
- Reports heuristic confidence levels (low/medium/high); these levels are not statistically calibrated.
- Builds a plan with candidate engines and required input roles, while keeping every engine `planned` and execution disabled.
- Exposes `GET /api/v1/agent/status` to report identity, local/model-independent runtime, capabilities, and limitations.
- Uses no model weights, remote inference API, or network dependency for request routing.

## Clarification behavior

If the request does not match a supported domain, the agent does **not** silently classify it as GIS. It returns:

- `classification_status: needs_clarification`;
- `next_action: ask_clarification`;
- an Arabic or English clarification question;
- no fabricated specialist, engine, or required inputs.

Data readiness is marked `not_assessed` in this case. A missing domain is not treated as an empty-but-complete data checklist.

## Data readiness and scientific safety

Dataset upload may include `X-Data-Role`. When a request is classified, the API compares required input roles with role-tagged datasets in the project and records available/missing roles. A role is user-supplied metadata, not proof of file contents.

Even if every required role is present, execution remains blocked until a scientific engine is integrated, pinned, tested, and reviewed. Plans are not scientific results, drilling recommendations, resource estimates, or professional certification.

## Multilingual routing extension

The deterministic intent catalog now recognizes geoscience terms in Arabic, English, Russian, and Chinese for groundwater/hydrology, 3D geology, seismology, mineral exploration, remote sensing, and GIS.

- Matching is Unicode-normalized, case-insensitive, and phrase-boundary-aware.
- Russian terms include common topic phrases; Chinese terms include domain-specific contiguous phrases.
- The original matched terms are returned as routing evidence in their source script.
- Domain labels and heuristic confidence are translated in the Arabic/English plan interface.
- This is a curated keyword lexicon, not general multilingual understanding. Unsupported wording still triggers clarification, and confidence remains heuristic—not calibrated.
