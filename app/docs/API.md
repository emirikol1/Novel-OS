# Novel OS HTTP API

Base path: `/api`. Project id is the folder name under the projects root.

This document highlights Story Graph and deduplication endpoints added for the graph workflow. Other routes (chapters, characters, pipeline jobs) follow the same patterns as the FastAPI router in `api/routes.py`.

## Story Graph CRUD

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects/{id}/story-graph/nodes` | List nodes |
| POST | `/projects/{id}/story-graph/nodes` | Create node |
| PATCH | `/projects/{id}/story-graph/nodes/{node_id}` | Update node |
| DELETE | `/projects/{id}/story-graph/nodes/{node_id}` | Delete node (rewires briefs, drops edges) |
| GET | `/projects/{id}/story-graph/edges` | List edges |
| POST | `/projects/{id}/story-graph/edges` | Create edge |
| PATCH | `/projects/{id}/story-graph/edges/{edge_id}` | Update edge |
| DELETE | `/projects/{id}/story-graph/edges/{edge_id}` | Delete edge |
| POST | `/projects/{id}/story-graph/migrate` | Body: `{ "force": false }` — copy plot threads into graph |

## Story Graph duplicates

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects/{id}/story-graph/duplicates` | Heuristic scan for similar nodes |
| POST | `/projects/{id}/story-graph/duplicates/merge` | Merge members into keep node |
| POST | `/projects/{id}/story-graph/duplicates/auto-resolve` | Auto-merge ≥95% confidence groups |

### Merge request body

```json
{
  "keep_id": "graph_node_001",
  "merge_ids": ["graph_node_002"],
  "title_override": ""
}
```

### Duplicate report shape

```json
{
  "groups": [
    {
      "confidence": 0.95,
      "reason": "Similar graph nodes (beat): Vault alarm, Vault Alarm",
      "suggested_keep_id": "graph_node_001",
      "members": [
        { "id": "graph_node_001", "label": "Vault alarm", "node_kind": "beat" },
        { "id": "graph_node_002", "label": "Vault Alarm", "node_kind": "beat" }
      ]
    }
  ],
  "source": "heuristic"
}
```

## Legacy entity duplicates (unchanged)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects/{id}/duplicates` | Characters + plot threads (`?ai=true` for AI file) |
| POST | `/projects/{id}/duplicates/merge` | Merge characters or plot threads |
| POST | `/projects/{id}/duplicates/auto-resolve` | Auto-merge high-confidence entity groups |

## Chapter briefs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects/{id}/chapters/{n}/brief` | Load brief |
| PUT | `/projects/{id}/chapters/{n}/brief` | Save brief |
| DELETE | `/projects/{id}/chapters/{n}/brief` | Remove brief |

## Story bible duplicates (unchanged)

| Method | Path |
|--------|------|
| GET | `/projects/{id}/story-bible/duplicates` |
| POST | `/projects/{id}/story-bible/duplicates/merge` |
| POST | `/projects/{id}/story-bible/duplicates/auto-resolve` |
