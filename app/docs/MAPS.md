# Map Image + Location Pins

The **Map** tab lets authors upload a world map image per project map record and place **normalized pins** (x/y from 0–1) with labels, optional lore section/label references, and notes. Map images live under `assets/maps/`; pin metadata lives in SQLite.

**Important:** Pins **do not** mutate Story Bible entries or `Character.current_location`. Optional lore fields are navigation hints — click-through opens the Story Bible tab when configured.

---

## Author workflow

1. Open **Map** tab.
2. Create a map (default name **Main Map**) if none exists; multiple maps per project are supported.
3. Upload a map image (PNG, JPEG, WebP, GIF — validated server-side).
4. Enable **Add pin** mode and click the image to place a pin, or drag existing pins.
5. Edit pin label, coordinates, lore section, lore label, and notes in the pin modal.
6. Click a pin with lore metadata → **Story Bible** tab (best-effort section routing).

```mermaid
flowchart LR
    Upload["POST .../maps/{id}/image"]
    Assets["assets/maps/{map_id}/"]
    PinsAPI["/maps/{id}/pins CRUD"]
    SQLite["map_pin + project_map tables"]
    Panel["MapPanel"]

    Upload --> Assets
    Panel --> PinsAPI
    PinsAPI --> SQLite
    Assets --> Panel
```

---

## Data model

### Project map (SQLite `project_map`)

| Field | Notes |
|---|---|
| `id` | UUID |
| `name` | Display name |
| `image_filename` | Stored file under `assets/maps/{map_id}/` |
| `created_at` / `updated_at` | Timestamps |

### Map pin (SQLite `map_pin`)

| Field | Notes |
|---|---|
| `id` | UUID |
| `map_id` | Parent map |
| `label` | Required display name |
| `x`, `y` | Float 0–1, normalized to image dimensions |
| `lore_section` | Optional bible section key |
| `lore_label` | Optional entry label (not auto-synced to bible) |
| `notes` | Author notes |

---

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/projects/{id}/maps` | List maps |
| `POST` | `/api/projects/{id}/maps` | Create map |
| `GET` | `/api/projects/{id}/maps/{map_id}` | Map + pins |
| `PATCH` | `/api/projects/{id}/maps/{map_id}` | Rename |
| `DELETE` | `/api/projects/{id}/maps/{map_id}` | Delete map and assets |
| `POST` | `/api/projects/{id}/maps/{map_id}/image` | Upload image |
| `GET` | `/api/projects/{id}/maps/{map_id}/image` | Serve image bytes |
| `GET/POST/PATCH/DELETE` | `.../maps/{map_id}/pins[/{pin_id}]` | Pin CRUD |

Frontend: `api.projectMaps`, `mapImageUrl`, `api.createMapPin`, etc.

---

## Functional boundaries

- **No Story Bible mutation** — lore fields are references only.
- **No mention intelligence** — pins do not update `[[lore:…]]` mentions or reviewed location memory.
- **Not** included in Markdown or EPUB export.
- Map images are **not** under `outputs/` — see backup notes below.

---

## Backup and export considerations

Portable project package and named backups zip **`outputs/`**, **`assets/maps/`**, **`assets/portraits/`**, plus `db_export.json` (including `project_maps` and `map_pins`).

See [EXPORTS.md](EXPORTS.md).

---

## Known limitations

- One image per map record (no layered or regional overlays).
- Pin lore labels are not validated against live bible content.
- No sync with free-text `Character.current_location`.
- No geospatial projection — coordinates are flat image percentages only.

---

## Source files

| File | Role |
|---|---|
| `web/src/components/MapPanel.tsx` | Upload, pin placement, drag |
| `web/src/lib/mapPins.ts` | Coordinate helpers |
| `api/map_assets.py` | Safe image storage |
| `api/db.py` | SQLite CRUD |
| `tests/test_maps_api.py` | API and path-safety tests |

See [EXPORTS.md](EXPORTS.md) and [API.md](API.md).
