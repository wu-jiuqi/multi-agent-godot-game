---
name: prepare-game-project-brief
description: Turn a game owner's provided gameplay, art direction, implementation outline, constraints, and source documents into an auditable project brief for staffing design. Use after pipeline bootstrap and before organization design, or when project direction changes require the staffing baseline to be rebuilt and reconfirmed.
---

# Prepare Game Project Brief

Coordinate project definition as the Project Manager role without inventing direction or taking ownership from later domain agents.

## Required Context

- Validate the project instance and read `game-pipeline/project-definition/project-brief.yaml`.
- Read `../../agents/pipeline-director.md`, `../../contracts/project-brief.template.yaml`, the project `AGENTS.md`, and registered fact sources.
- Treat the project owner as the authority for gameplay direction, art direction, scope, budget, platform, and initial implementation intent.

## Workflow

1. Register every source with a stable ID, location, version or digest, supplier, and authority. Preserve conflicting sources instead of silently choosing one.
2. Convert owner-provided plans into concise statements. Classify each as `confirmed`, `preference`, `hypothesis`, or `unknown`; never promote a preference or hypothesis to confirmed.
3. Cover project goal, gameplay, art direction, implementation outline, platform and engine, and scope constraints. Ask the owner about missing direction-changing information and preserve unanswered items as explicit unknowns.
4. Record open questions, risks, and responsibility needs. Describe responsibilities and expected artifacts without naming the final Agent or Department; organization design owns that mapping.
5. Set staffing readiness to `blocked` while a required domain is unknown or a blocking question remains. A readable document is not automatically staffing-ready.
6. Resolve the plugin root as two directories above this `SKILL.md`, then run `python <plugin-root>/scripts/validate_project_brief.py game-pipeline/project-definition/project-brief.yaml --project-id <project-id>`. Copy the reported `subject_digest` into the brief and rerun validation.
7. Show the owner the complete brief, changes from their source material, all assumptions and unknowns, staffing readiness, and exact subject digest. Stop for explicit confirmation.
8. After confirmation, create an immutable `project-brief` approval record with the same subject ID and digest, mark the brief `confirmed`, update its Fact Source binding to `project.definition.confirmed` with the current digest, and run the validator with `--approval-dir game-pipeline/approvals` plus the full project validator.
9. Route a confirmed, staffing-ready brief to `$design-game-organization`. If the owner changes approved content, mark the brief `revise`, invalidate the old approval for current use, increment the brief version, and repeat confirmation.

## Ownership Boundaries

- The Project Manager owns coordination, structure, source indexing, unknowns, risks, and change impact.
- The human owner approves direction and the brief baseline.
- The organization architect maps responsibility needs into staffing proposals.
- Approved game-design, art, content, technical, and QA roles later own their detailed domain documents.
- Bootstrap mode is a bounded workflow, not an unregistered formal Agent Instance.

## Failure Routing

- Contradictory sources or missing owner decisions return to the project owner.
- Invalid structure, stale digest, or missing approval returns to this workflow.
- Premature Department, Position, Preset, or Skill decisions return to organization design.
- Detailed gameplay, art, or technical specification requests wait for the approved domain owner unless the human explicitly keeps that decision.

Return the brief path and version, source index, classified statements, blocking questions, risks, responsibility needs, validation result, subject digest, confirmation status, and next legal action.
