#!/usr/bin/env bash
# PreToolUse hook: fires before git commit.
# If core source files are staged, tells Claude which .claude/rules/ files need updating.
# Never touches corrections_log.md or linting_validation.md.

CMD=$(jq -r '.tool_input.command // empty' 2>/dev/null)

# Only act on git commit commands
echo "$CMD" | grep -q '^git commit' || exit 0

# Check staged files
CHANGED=$(git diff --cached --name-only 2>/dev/null)

# If .claude/rules/ files are already staged, assume Claude already updated them — skip
echo "$CHANGED" | grep -q '^\.claude/rules/' && exit 0

# If no core files are staged, nothing to do
echo "$CHANGED" | grep -qE '^(backend/app|frontend/src|docker-compose\.yml)' || exit 0

# Build list of rules files that need updating based on what changed
TARGETS=""

echo "$CHANGED" | grep -qE '^(backend/app/services|backend/app/api|backend/app/models|backend/app/core|docker-compose\.yml)' \
  && TARGETS="${TARGETS} diagrams_data_flows.md"

echo "$CHANGED" | grep -qE '^(backend/requirements\.txt|frontend/package\.json|docker-compose\.yml)' \
  && TARGETS="${TARGETS} external_references.md"

echo "$CHANGED" | grep -qE '^(backend/app|frontend/src|docker-compose\.yml)' \
  && TARGETS="${TARGETS} project_annotaterl.md"

printf '{"systemMessage": "Core files are staged for commit. Before committing, run `git diff --cached` to review the changes, then update these .claude/rules/ files to reflect anything that is now factually different: %s. Be minimal — only change what the diff actually contradicts. Do NOT touch corrections_log.md or linting_validation.md. After updating, stage the rules files and re-run the commit."}\n' "$TARGETS"
