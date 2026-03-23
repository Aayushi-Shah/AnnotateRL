# AnnotateRL Project Context

Portfolio project targeting Anthropic RL org. Goal: demonstrate understanding of their internal RLHF/RLAIF data collection pipeline.

**Motivation framing (critical for README):** Every design decision ties back to RL org goals — data quality, researcher velocity, vendor workflows.

**Current work in progress (uncommitted as of 2026-03-23):**
- Fine-tuning feature: FineTuningJob + ModelVersion models, service, API router, migration 002, frontend page
- AI agent upgraded to OpenRouter (free models) with model version tracking and fallback chain
- Seed script: tasks now created as drafts (publish triggers AI generation)
- Frontend: .eslintrc.json added, ResearcherNav includes Fine-tuning link

**Key design tension:** StubProvider simulates training by default — intentional for portfolio demo (no GPU needed). The TrainingProvider protocol makes swapping in a real provider straightforward.
