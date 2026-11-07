"""The files Claude reads and writes when it, not Jev, chooses the clips.

`clipper prepare` writes transcript.txt; Claude reads it and writes picks.json;
`clipper render` turns picks.json into clips."""
from clipper.propose import at


def stamp(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def transcript(sents: list[dict], marks: dict[str, list[float]], meta: dict, trend: dict[str, float]) -> str:
    """Numbered sentences with timestamps, each tagged with the audience signals that point at it."""
    tags: dict[int, set[str]] = {}
    for tag, times in marks.items():
        for t in times:
            tags.setdefault(at(sents, t), set()).add(tag)
    hot = sorted(trend, key=lambda t: -trend[t])[:30]
    head = [
        f"# {meta['title']}",
        f"# channel: {meta.get('channel') or 'n/a'}  |  length: {stamp(sents[-1]['e'])}  |  sentences: {len(sents)}",
        "# tags: replayed = YouTube's most-replayed parts, comments = viewers posted this timestamp,",
        "#       loud = audio energy peak",
        f"# hashtags on popular Shorts about this video: {' '.join('#' + t for t in hot) or 'none found'}",
        "",
    ]
    lines = [f"[{k}] {stamp(s['s'])}-{stamp(s['e'])}"
             + (f" ({', '.join(sorted(tags[k]))})" if k in tags else "") + f" {s['text']}"
             for k, s in enumerate(sents)]
    return "\n".join(head + lines) + "\n"


def clips(picks: list[dict], sents: list[dict]) -> list[dict]:
    """Picks as written by Claude, made into the clip dicts render() takes."""
    out = []
    for p in picks:
        i, j = int(p["start"]), int(p["end"])
        if not 0 <= i <= j < len(sents):
            raise ValueError(f"pick {p} is outside sentences 0-{len(sents) - 1}")
        out.append({"i": i, "j": j, "s": sents[i]["s"], "e": sents[j]["e"],
                    "title": p.get("hook") or p.get("title", ""), "post_title": p.get("title", ""),
                    "description": p.get("description", ""),
                    "tags": [t.lstrip("#") for t in p.get("hashtags", [])]})
    return out
