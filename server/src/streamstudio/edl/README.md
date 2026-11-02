# edl

## Overview

The Edit Decision List: the pydantic model that is the single source of truth
for a project's edit (`model.py`), pure operations that return a new validated
EDL (`ops.py`), and a JSON Schema exporter (`export.py`, console script
`streamstudio-schema`) that the web app uses to generate matching TypeScript
types. `core.store` persists `EDL` instances as JSON in `edl_versions`.

## Interface

- Package re-exports (`__init__.py`): `EDL`, `Clip`, `Format`, `Marker`, `Track`, `EDLError`, `append_clip`, `delete_range`, `duration`, `new_edl`, `snap_to_frame`, `split`
- `model.TrackKind = Literal["video", "audio", "caption", "overlay"]`
- `model.Format` — `width`, `height`, `fps_num`, `fps_den`, `sample_rate`
- `model.Clip` — `id`, `asset_id`, `start`, `src_in`, `src_out`, `speed`, `volume`, `muted`; properties `duration`, `end`; `src_at(t)`
- `model.Track` — `id`, `kind`, `name`, `magnetic`, `muted`, `hidden`, `locked`, `clips`
- `model.Marker` — `id`, `at`, `label`, `kind: "chapter" | "note" | "short"`
- `model.EDL` — `schema_version`, `format`, `tracks`, `markers`; `track(track_id)`
- `ops.EDLError(ValueError)`, `ops.new_edl(fmt=None)`, `ops.duration(edl)`, `ops.snap_to_frame(t, fmt)`, `ops.append_clip(edl, track_id, asset_id, src_in, src_out, *, at=None)`, `ops.split(edl, track_id, at)`, `ops.delete_range(edl, start, end, *, track_ids=None, ripple=True)`
- `export.schema_json() -> str`, `export.main()`

## Invariants

- `[model.py]` All times are integer microseconds; every model uses `ConfigDict(extra="forbid")`, so unknown keys are rejected.
- `[model.py:Clip._in_before_out]` `src_out > src_in`. Field bounds: `start >= 0`, `src_in >= 0`, `src_out > 0`, `0 < speed <= 16`, `0 <= volume <= 4`.
- `[model.py:Track._no_overlaps]` Clips on a track never overlap; validation sorts `clips` by `start`.
- `[model.py:EDL._unique_ids]` Track and clip ids are unique across the whole document. `schema_version` is `Literal[1]`; the schema title is `StreamStudioEDL`.
- `[ops.py:_editable]` Operations raise `EDLError` for an unknown track or a `locked` track. Every operation returns a new `EDL` built through `EDL.model_validate` (`_rebuild`); the input is not mutated.
- `[ops.py:new_edl]` A new EDL has tracks `V1` (video, `magnetic=True`), `V2` (overlay), `A1` (audio), `C1` (caption).
- `[ops.py:split]` raises `EDLError` when no clip strictly contains `at`; the new tail clip gets a fresh id. `[ops.py:delete_range]` requires `end > start`, defaults to every unlocked track, and with `ripple` shifts later clips left by `end - start`.
- `[ops.py:snap_to_frame]` rounds to the nearest frame boundary derived from `fps_num/fps_den`.

## Side Effects

- `[export.py:main]` writes the schema to the path given as `argv[1]` (creating parent directories) or to stdout.
- `[ops.py]` calls `core.ids.new_id("clip")`, which reads the clock and `secrets`; otherwise the module is pure.

## Verification

- Run: `cd server && .venv/bin/python -m pytest`
- Lint: `cd server && .venv/bin/ruff check src tests`
