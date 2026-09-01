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
    ├── .cache/migrations/          # 迁移逐字节备份（Git 忽略）
    ├── assets/
    │   ├── contracts/              # 专业资产每个 revision 的 Contract
    │   ├── budgets/                # 项目批准的预算 Profile
    │   ├── evidence/               # 导入、性能、评审与授权证据
    │   ├── rights/                 # 许可证、合同与取得证明
    │   └── protected-path-snapshots/ # UI 等只读事实源摘要
    ├── loops/
    │   ├── contracts/              # 项目采用的版本化 Loop Contract
    │   └── registry/               # 循环 Snapshot/Event；资产只存引用与 Gate 证据
    ├── project-definition/         # 经确认的项目文档基线与编制输入
    └── organization/
        ├── snapshot.yaml
        ├── event-history.yaml
        ├── change-sets/
        ├── validations/
        └── views/
```

除 `.runtime/`、`.cache/`、`tmp/`、临时原始证据与生成 SVG 外，`game-pipeline/` 应由项目 Git 跟踪。
