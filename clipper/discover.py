"""Find source videos worth clipping: this month's most-viewed, ranked by views per day."""
import math
import re
from collections import Counter
from datetime import date, datetime
from urllib.parse import quote

from yt_dlp import YoutubeDL

# sp: videos uploaded this month, most-viewed first
SEARCH = "https://www.youtube.com/results?search_query={}&sp=CAMSBAgEEAE%253D"
BASE = {"quiet": True, "no_warnings": True, "js_runtimes": {"node": {}, "deno": {}}}


def discover(cfg: dict, seen: set[str], limit: int) -> list[dict]:
    """The `limit` fastest-growing videos from cfg's searches and channels, skipping `seen` ids."""
    found = {}
    with YoutubeDL(BASE | {"extract_flat": True, "playlistend": cfg["per_source"], "ignoreerrors": True}) as ydl:
        for src in [SEARCH.format(quote(q)) for q in cfg["queries"]] + cfg["channels"]:
            for v in (ydl.extract_info(src, download=False) or {}).get("entries") or []:
                if (v and v["id"] not in seen and (v.get("view_count") or 0) >= cfg["min_views"]
                        and cfg["min_minutes"] * 60 <= (v.get("duration") or 0) <= cfg["max_minutes"] * 60):
                    found[v["id"]] = v
    # Upload dates only come with a full lookup, so spend those on the most-viewed.
    top = sorted(found.values(), key=lambda v: -v["view_count"])[:limit * 3]
    out = []
    with YoutubeDL(BASE | {"skip_download": True, "ignoreerrors": True}) as ydl:
        for v in top:
            info = ydl.extract_info(v["id"], download=False)
            if not info or not (info.get("language") or cfg["language"]).startswith(cfg["language"]):
                continue
            days = max((date.today() - datetime.strptime(info["upload_date"], "%Y%m%d").date()).days, 1)
            out.append({"url": info["webpage_url"], "title": info["title"], "channel": info.get("channel") or "",
                        "views": info["view_count"], "days": days, "per_day": info["view_count"] / days})
    return sorted(out, key=lambda v: -v["per_day"])[:limit]


def trending_tags(queries: list[str]) -> dict[str, float]:
    """Hashtags on this month's most-viewed Shorts for each query, weighted by how many
    Shorts use them and how many views those got."""
    shorts = {}
    with YoutubeDL(BASE | {"extract_flat": True, "playlistend": 40, "ignoreerrors": True}) as ydl:
        for q in queries:
            for v in (ydl.extract_info(SEARCH.format(quote(f"{q} #shorts")), download=False) or {}).get("entries") or []:
                if v and (v.get("duration") or 999) <= 180:
                    shorts[v["id"]] = v
    weight, uses = Counter(), Counter()
    # Hashtags mostly sit in descriptions, which need a full lookup, so read the top few.
    with YoutubeDL(BASE | {"skip_download": True, "ignoreerrors": True}) as ydl:
        for v in sorted(shorts.values(), key=lambda v: -(v.get("view_count") or 0))[:12]:
            info = ydl.extract_info(v["id"], download=False) or v
            text = f"{info.get('title') or ''} {info.get('description') or ''}"
            for tag in {t.lower() for t in re.findall(r"#(\w+)", text)}:
                weight[tag] += math.log10((info.get("view_count") or 0) + 10)
                uses[tag] += 1
    # A tag on a single Short is usually that uploader's own name or brand.
    return {t: w for t, w in weight.items() if uses[t] > 1}
