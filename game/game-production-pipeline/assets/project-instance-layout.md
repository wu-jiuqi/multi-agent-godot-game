# 项目实例目录

```text
<project>/
├── .agents/skills/                 # 项目专属 Skills
├── .codex/agents/                  # 由批准的 Agent Preset 生成的 Codex TOML
└── game-pipeline/
    ├── project.yaml
    ├── plugin-lock.yaml
    ├── agents/                     # 项目 Agent Presets
    ├── approvals/                  # 人工审批记录
    ├── bindings/                   # Skill 与事实源绑定
    ├── loops/                      # 生产循环实例
    ├── project-definition/         # 经确认的项目文档基线与编制输入
    └── organization/
        ├── snapshot.yaml
        ├── event-history.yaml
        ├── change-sets/
        ├── validations/
        └── views/
```

除 `.runtime/`、`.cache/`、`tmp/`、临时原始证据与生成 SVG 外，`game-pipeline/` 应由项目 Git 跟踪。
