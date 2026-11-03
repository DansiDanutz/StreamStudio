"""The episode factory's job handlers, registered with the worker.

Imported by `worker/main.py` (never by `worker/handlers.py`, so there is no cycle). Every
handler imports its module inside the function, so importing this file pulls no heavy library.
Every handler is idempotent: a repeated run finds its output and returns. Handlers report by
writing files; the planner reads the record and the files.
"""

from __future__ import annotations

import contextlib
import json
from typing import Any

from ..worker.handlers import JobContext, handler


def _payload(ctx: JobContext) -> dict[str, Any]:
    p = ctx.job.get("payload") or {}
    return json.loads(p) if isinstance(p, str) else p


def _enqueue_planner(ctx: JobContext, episode_id: str) -> None:
    from ..core import store

    store.enqueue(
        ctx.conn, "episode_advance", project_id=ctx.job.get("project_id"),
        payload={"episode_id": episode_id},
    )  # fmt: skip


@handler("episode_advance")
def episode_advance(ctx: JobContext) -> dict[str, Any]:
    from . import planner

    return planner.advance(ctx.conn, ctx.settings, _payload(ctx)["episode_id"])


@handler("scene_qa")
def scene_qa(ctx: JobContext) -> dict[str, Any]:
    from . import qa, record

    p = _payload(ctx)
    s = ctx.settings
    ep = record.load(ctx.conn, p["episode_id"])
    if ep is None:
        raise ValueError("episode no longer exists")
    scene = next(sc for sc in ep.script.scenes if sc.id == p["scene_id"])
    key = p["key"]
    clip, _ = record.clip_paths(s, key)
    first_key = record.scene_key(s, scene, ep.render_script(), 0)
    report = qa.inspect(record.episode_dir(s, ep.id) / "qa" / scene.id, key, clip, s,
                        scene.spoken, first_key)
    _enqueue_planner(ctx, ep.id)
    return report


@handler("scene_compose")
def scene_compose(ctx: JobContext) -> dict[str, Any]:
    """One scene's clip and cut-out → `scenes/<scene>.mp4`, with its inputs hash beside it."""
    from . import compose, connected_cards, record, website_demo

    p = _payload(ctx)
    s = ctx.settings
    ep = record.load(ctx.conn, p["episode_id"])
    if ep is None:
        raise ValueError("episode no longer exists")
    script = ep.render_script()
    scene = next(sc for sc in script.scenes if sc.id == p["scene_id"])
    st = ep.record["scenes_state"].get(scene.id, {})
    key = st.get("clip_key") or record.scene_key(s, scene, script, int(st.get("take", 0)))
    mp4, webm = record.clip_paths(s, key)
    if not mp4.exists():
        raise ValueError(f"{scene.id}: the clip {key} is missing")
    d = record.episode_dir(s, ep.id)
    out = d / "scenes" / f"{scene.id}.mp4"
    hash_file = d / "scenes" / f"{scene.id}.hash"
    card = d / "cards" / f"{st['card_id']}.mp4" if st.get("card_id") else None
    if scene.plan and scene.plan.website_demo:
        card = website_demo.prepare(s, scene, d)
    current = record.inputs_hash(
        scene, mp4, webm, card, degraded=st.get("qa") == "degraded",
        look=ep.channel_settings.get("look"),
    )
    if out.exists() and hash_file.exists() and hash_file.read_text().strip() == current:
        result = {"scene": scene.id, "skipped": True}
    else:
        ctx.progress(0.05, f"composing {scene.id}")
        if scene.plan and scene.plan.connected_cards:
            result = connected_cards.render(s, scene.plan.connected_cards,
                                            ep.channel_settings.get("name", "DansLab"), mp4, out)
        else:
            result = compose.compose_scene(
                s, scene, mp4, webm, out, card_mp4=card, degraded=st.get("qa") == "degraded",
                compositor=compose.Compositor(s, ep.channel_settings.get("look")),
                progress=lambda f, m: ctx.progress(0.05 + 0.9 * f, m),
            )  # fmt: skip
        hash_file.write_text(current)
        result["scene"] = scene.id
    _enqueue_planner(ctx, ep.id)
    return result


@handler("episode_assemble")
def episode_assemble(ctx: JobContext) -> dict[str, Any]:
    """The composed scenes + intro + bed + SFX → `final.mp4` and `final.cues.json`."""
    from . import mix, record

    p = _payload(ctx)
    s = ctx.settings
    ep = record.load(ctx.conn, p["episode_id"])
    if ep is None:
        raise ValueError("episode no longer exists")
    script = ep.render_script()
    d = record.episode_dir(s, ep.id)
    final = d / "final.mp4"
    if final.exists():
        _enqueue_planner(ctx, ep.id)
        return {"skipped": True}
    files = [d / "scenes" / f"{sc.id}.mp4" for sc in script.scenes]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        raise ValueError(f"composed scenes missing: {', '.join(missing)}")
    ctx.progress(0.1, "assembling")
    sound = ep.channel_settings.get("sound")
    intro = s.assets_dir / "brand" / "danslab-intro.mp4"
    if sound is not None and "intro" in sound:
        from .channel_files import verify

        intro = verify(s, sound["intro"], kind="intro") if sound["intro"] else None
    result = mix.assemble(
        s, script.scenes, files, intro, final,
        sound=mix.Sound.model_validate(sound) if sound is not None else None,
    )
    (d / "assemble.json").write_text(json.dumps(result, indent=1))
    _enqueue_planner(ctx, ep.id)
    return result


@handler("episode_publish_kit")
def episode_publish_kit(ctx: JobContext) -> dict[str, Any]:
    """`kit.json` and `final.srt` from the script and the assembled timings."""
    from . import kit, record

    p = _payload(ctx)
    s = ctx.settings
    ep = record.load(ctx.conn, p["episode_id"])
    if ep is None:
        raise ValueError("episode no longer exists")
    d = record.episode_dir(s, ep.id)
    kit_json = d / "kit.json"
    if kit_json.exists() and (d / "final.srt").exists():
        _enqueue_planner(ctx, ep.id)
        return {"skipped": True}
    timing = json.loads((d / "assemble.json").read_text())
    starts = [t - timing["intro_s"] for t in timing["starts"]]
    words: dict[str, list[dict]] = {}
    for sc in ep.script.scenes:
        key = ep.scene_state(sc.id).get("qa_key")
        wf = d / "qa" / sc.id / f"{key}.words.json"
        if wf.exists():
            with contextlib.suppress(json.JSONDecodeError):
                words[sc.id] = [
                    {"start": w["start_ms"]/1000, "end": w["end_ms"]/1000, "word": w["word"]}
                    for w in json.loads(wf.read_text()).get("words", [])
                ]
    k, srt = kit.build_kit(ep.script, starts, timing["durations"], timing["intro_s"], words)
    publishing = ep.channel_settings.get("publish", {})
    footer = publishing.get("description_footer")
    if footer:
        k["description"] = (k["description"] + "\n\n" + footer).strip()
    k["tags"] = list(dict.fromkeys([*k["tags"], *publishing.get("default_tags", [])]))
    (d / "final.srt").write_text(srt)
    kit_json.write_text(json.dumps(k, indent=1, ensure_ascii=False))
    _enqueue_planner(ctx, ep.id)
    return {"chapters": len(k["chapters"]), "notes": k["notes"]}


@handler("episode_register")
def episode_register(ctx: JobContext) -> dict[str, Any]:
    """`final.mp4` → the recordings library as `rec_<stamp>-ep`."""
    from ..core.db import tx
    from . import kit, record

    p = _payload(ctx)
    s = ctx.settings
    with tx(ctx.conn):
        ep = record.load(ctx.conn, p["episode_id"])
        if ep is None:
            raise ValueError("episode no longer exists")
        existing = kit.registered_recording(s, ep.id, ep.record.get("revision", 0))
        d = record.episode_dir(s, ep.id)
        if existing and (s.recordings_dir / f"{existing}.mp4").exists():
            _enqueue_planner(ctx, ep.id)
            return {"recording_id": existing, "skipped": True}
        final = d / "final.mp4"
        if not final.exists():
            raise ValueError("final.mp4 is missing")
        k = json.loads((d / "kit.json").read_text())
        revision = ep.record.get("revision", 0)
        result = kit.register(s, ep.id, final, d / "final.srt", k, revision=revision,
                              language=ep.channel_settings.get("language", "en"))
        _enqueue_planner(ctx, ep.id)
        return result


@handler("episode_purge")
def episode_purge(ctx: JobContext) -> dict[str, Any]:
    """The Purge button: remove the workings, keep the final video, the kit and the record."""
    from ..core.db import tx
    from . import publish, record

    p = _payload(ctx)
    s = ctx.settings
    with tx(ctx.conn):
        ep = record.load(ctx.conn, p["episode_id"])
        if ep is None:
            raise ValueError("episode no longer exists")
        if ep.status not in ("published", "cancelled", "purged"):
            raise ValueError(f"purge is for published or cancelled episodes, not {ep.status}")
        result = publish.purge(s, ep)
        if ep.status != "purged":
            record.set_status(
                ep, "purged", f"workings purged: {result['freed_bytes'] / 1e6:.0f} MB freed"
            )
        record.save(ctx.conn, ep)
    return result


@handler("channel_intro")
def channel_intro(ctx: JobContext) -> dict[str, Any]:
    from ..core.db import tx
    from . import profiles
    from .channel_intro import generate, selected_fonts

    p = _payload(ctx)
    source = profiles.get(ctx.conn, p["slug"], p["version"])
    if not source or source["hash"] != p["hash"]:
        raise ValueError("the selected channel version no longer exists")
    profile = profiles.Profile.model_validate(source["profile"])
    digest = generate(ctx.settings, profile)
    with tx(ctx.conn):
        latest = profiles.get(ctx.conn, p["slug"])
        if not latest:
            return {"discarded": True, "reason": "channel removed during rendering"}
        current = profiles.Profile.model_validate(latest["profile"])
        previous_sound = profile.sound or profiles.Sound()
        current_sound = current.sound or profiles.Sound()
        if (current.name != profile.name or current.intro != profile.intro
                or selected_fonts(current) != selected_fonts(profile)
                or current_sound.sfx != previous_sound.sfx
                or current_sound.levels.intro != previous_sound.levels.intro
                or current_sound.intro not in (previous_sound.intro, digest)):
            return {"discarded": True, "reason": "channel changed during rendering"}
        if current_sound.intro == digest:
            return {"slug": p["slug"], "version": latest["version"], "intro": digest}
        profile = current
        if profile.sound is None:
            profile.sound = profiles.Sound()
        profile.sound.intro = digest
        saved = profiles.save(ctx.conn, profile, latest["version"] + 1)
    return {"slug": p["slug"], "version": saved["version"], "intro": digest}
