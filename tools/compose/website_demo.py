"""Inspect the card rules, capture an approved scene, or recompose from existing assets."""
import argparse
import json
from pathlib import Path

from streamstudio.core.config import Settings
from streamstudio.episode import website_demo
from streamstudio.episode.contract import Scene, WebsiteDemo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("catalog")
    for name in ("prepare", "preview"):
        cmd = sub.add_parser(name)
        cmd.add_argument("scene", type=Path, help="one Scene from a StreamStudio script")
        cmd.add_argument("workspace", type=Path, help="per-episode asset directory")
        if name == "preview":
            cmd.add_argument("base", type=Path, help="1920x1080 narrated scene MP4, 25 fps")
            cmd.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "catalog":
        print(json.dumps({**website_demo.CATALOG, "schema": WebsiteDemo.model_json_schema()}))
        return
    s = Settings()
    scene = Scene.model_validate_json(args.scene.read_bytes())
    if args.command == "prepare":
        print(website_demo.prepare(s, scene, args.workspace))
        return
    card = website_demo.asset_path(args.workspace, scene)
    if not card or not card.is_file():
        parser.error("prepare this capture before previewing")
    website_demo.overlay(s, args.base, card, scene.plan.website_demo, args.output)


if __name__ == "__main__":
    main()
