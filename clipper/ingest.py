"""Fetch a video plus the audience signals that come with it."""
import json
import re
from pathlib import Path

from yt_dlp import YoutubeDL


def ingest(src: str, root: Path, browser: str | None = None, video: bool = True) -> Path:
    """Returns the work dir holding meta.json and the media. `video=False` fetches audio only."""
    local = Path(src)
    if local.exists():
        work = root / re.sub(r"\W+", "_", local.stem)
        work.mkdir(parents=True, exist_ok=True)
        meta = {"id": work.name, "title": local.stem, "path": str(local.resolve()), "video": True}
        (work / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return work

    # The video id is only known after asking YouTube, so remember which dir each URL landed in.
    index = root / "index.json"
    known = json.loads(index.read_text(encoding="utf-8")) if index.exists() else {}
    if src in known and (root / known[src] / "meta.json").exists():
        work = root / known[src]
        meta = json.loads((work / "meta.json").read_text(encoding="utf-8"))
        if Path(meta["path"]).exists() and (meta["video"] or not video):
            return work

    opts = {
        "quiet": True,
        "noprogress": True,
        "format": "bv*[height<=1080]+ba/b" if video else "ba/b",
        "outtmpl": str(root / "%(id)s" / ("source" if video else "audio") / "media.%(ext)s"),
        "js_runtimes": {"node": {}, "deno": {}},
        "getcomments": True,
        "extractor_args": {"youtube": {"max_comments": ["300", "all", "0", "0"],
                                       "comment_sort": ["top"]}},
    }
    if video:
        opts["merge_output_format"] = "mp4"
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(src, download=True)
    work = root / info["id"]
    meta = {
        "id": info["id"],
        "title": info["title"],
        "url": info["webpage_url"],
        "channel": info.get("channel") or "",
        "tags": info.get("tags") or [],
        "path": str(Path(info["requested_downloads"][0]["filepath"]).resolve()),
        "video": video,
        "heatmap": info.get("heatmap") or [],
        "comments": [{"text": c.get("text") or "", "likes": c.get("like_count") or 0}
                     for c in info.get("comments") or []],
    }
    (work / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    root.mkdir(parents=True, exist_ok=True)
    index.write_text(json.dumps(known | {src: info["id"]}), encoding="utf-8")
    return work
