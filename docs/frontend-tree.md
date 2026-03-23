# Frontend Structure

> Auto-generated on 2026-03-23 23:05 UTC. Do not edit manually.

## Pages (App Router)

| Route | File |
|-------|------|
| `/annotator/my-tasks` | `src/app/annotator/my-tasks/page.tsx` |
| `/annotator/queue` | `src/app/annotator/queue/page.tsx` |
| `/annotator/workspace/:assignmentId` | `src/app/annotator/workspace/[assignmentId]/page.tsx` |
| `/login` | `src/app/login/page.tsx` |
| `/` | `src/app/page.tsx` |
| `/researcher/dashboard` | `src/app/researcher/dashboard/page.tsx` |
| `/researcher/datasets` | `src/app/researcher/datasets/page.tsx` |
| `/researcher/finetune` | `src/app/researcher/finetune/page.tsx` |
| `/researcher/tasks/:id` | `src/app/researcher/tasks/[id]/page.tsx` |
| `/researcher/tasks/new` | `src/app/researcher/tasks/new/page.tsx` |
| `/researcher/tasks` | `src/app/researcher/tasks/page.tsx` |

## Layouts

- `src/app/annotator/layout.tsx`
- `src/app/layout.tsx`
- `src/app/researcher/layout.tsx`

## Components

### annotations/
- `AnnotationWorkspace.tsx`
- `BinarySignal.tsx`
- `ComparisonSignal.tsx`
- `CorrectionSignal.tsx`
- `RatingSignal.tsx`

### dashboard/
- `OverviewCards.tsx`
- `RewardDistributionChart.tsx`
- `ThroughputChart.tsx`

### layout/
- `AnnotatorNav.tsx`
- `ResearcherNav.tsx`

### tasks/
- `TaskCard.tsx`
- `TaskForm.tsx`

### ui/
- `badge.tsx`
- `button.tsx`
- `card.tsx`
- `input.tsx`
- `label.tsx`
- `skeleton.tsx`
- `textarea.tsx`

## Library (src/lib/)

- `api.ts`
- `auth.ts`
- `types.ts`
- `utils.ts`
