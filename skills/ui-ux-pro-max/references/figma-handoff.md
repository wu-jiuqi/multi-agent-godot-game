# Legacy Figma UI handoff compatibility

Penpot MCP is the repository default. New UI visual work must follow [`penpot-handoff.md`](penpot-handoff.md), bind `provider: penpot`, `integration: penpot_mcp`, `tool:penpot-mcp`, and record `file_id`, `page_id`, and `shape_id`. The server URL and token are configured in the Codex host and are never committed.

Existing projects may retain a Figma handoff while they migrate. The legacy fields map as follows:

| Legacy Figma field | Penpot canonical field |
|---|---|
| `figma_visual_system` | `penpot_visual_system` |
| `figma_prototype` | `penpot_prototype` |
| `provider: figma` | `provider: penpot` |
| `integration: codex_figma_plugin` | `integration: penpot_mcp` |
| `tool:figma-codex-plugin` | `tool:penpot-mcp` |
| `file_key` | `file_id` |
| `frame_node_id` | `shape_id` |
| `frame_url` | `shape_url` |

Figma links and snapshots remain provenance for legacy records only. They are not the default integration and do not imply that the current Codex host is connected to Penpot. Keep the original `figma-handoff.md` reference until the project rewrites its contract; validators should accept either legacy Figma or canonical Penpot records during the migration window.
