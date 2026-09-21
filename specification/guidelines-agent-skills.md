# Runtime Skills Guidelines

## When to Create Runtime Skills
Create a runtime skill when:
- Complex multi-step workflows (approval processes, escalation paths)
- Domain-specific knowledge (compliance rules, validation constraints)
- Task-specific instructions that would bloat the system prompt
- Reference material needed (templates, lookup tables, examples)

## SKILL.md Format
```markdown
---
name: skill-name
description: What this skill does
---
# Skill Title
## Instructions
[Step-by-step instructions]
```

## Structure
```
assets/<asset-name>/app/skills/
└── <skill-name>/
    ├── SKILL.md
    └── references/  (optional)
```

Skills are loaded on-demand via the `load(path)` tool — no extra wiring needed.
