# Phase 3 — Chief-agent planning and data readiness

The deterministic coordinator is now labeled with the chief agent's public identity,
**المهندس الجمهوري**, and assigns domain roles by matched intent. This is a
rule-based routing layer, not an LLM and not a claim of autonomous reasoning.

Dataset upload may include `X-Data-Role`. Accepted roles correspond to the
planner's required inputs. Each new job compares required inputs against role-tagged
datasets already stored in that project and records:

- available inputs;
- missing inputs;
- whether the data-role checklist is complete;
- explicit execution block.

Even when the checklist is complete, execution remains blocked until a scientific
engine is integrated, pinned, tested, and certified. A file's role is user-supplied
metadata; it is not independently verified from its contents.
