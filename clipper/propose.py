"""Candidate clips. Recall matters here: a missed moment can't be recovered later,
while a bad candidate only costs one cheap Jev call."""
import math
import re
from bisect import bisect_right
from collections import Counter

from clipper.perceive import HOP

TS = re.compile(r"(?<!\d)(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?!\d)")
HOOK_P = 0.6


def peaks(values: list[float], times: list[float], k: int, gap: float = 20) -> list[float]:
    """Times of the k highest values that are at least `gap` seconds apart."""
    out = []
    for i in sorted(range(len(values)), key=lambda i: -values[i]):
        if all(abs(times[i] - t) >= gap for t in out):
            out.append(times[i])
            if len(out) == k:
                break
    return out


def comment_times(comments: list[dict], dur: float, k: int) -> list[float]:
    """Moments viewers point at with a timestamp, weighted by likes."""
    hits = Counter()
    for c in comments:
        for h, m, s in TS.findall(c["text"]):
            t = int(h or 0) * 3600 + int(m) * 60 + int(s)
            if 0 < t < dur:
                hits[t // 10] += 1 + math.log1p(c["likes"])
    return [b * 10 for b, _ in hits.most_common(k)]


def spans(sents: list[dict], starts, min_len: float, max_len: float) -> set[tuple[int, int]]:
    """Sentence ranges beginning at each start, at three lengths between min and max."""
    out = set()
    for i in starts:
        for f in (0.25, 0.6, 1.0):
            target = min_len + (max_len - min_len) * f
            j = i
            while j + 1 < len(sents) and sents[j + 1]["e"] - sents[i]["s"] <= target:
                j += 1
            if sents[j]["e"] - sents[i]["s"] >= min_len:
                out.add((i, j))
    return out


def anchors(sents: list[dict], meta: dict, loud: list[float], use_heatmap: bool = True) -> dict[str, list[float]]:
    """Moments the audience or the audio points at, as times in seconds per signal."""
    dur = sents[-1]["e"]
    k = max(3, int(dur / 60))
    # The opening seconds of any video are replayed by everyone who starts it.
    heat = [h for h in meta.get("heatmap") or [] if h["start_time"] > 0] if use_heatmap else []
    smooth = [sum(loud[i:i + 20]) / 20 for i in range(max(len(loud) - 20, 1))]
    return {
        "replayed": peaks([h["value"] for h in heat], [h["start_time"] for h in heat], k),
        "comments": comment_times(meta.get("comments") or [], dur, k),
        "loud": peaks(smooth, [i * HOP for i in range(len(smooth))], k),
    }


def at(sents: list[dict], t: float) -> int:
    """Index of the sentence playing at time t."""
    return max(bisect_right([s["s"] for s in sents], t) - 1, 0)


def propose(sents, meta, loud, hook_p, min_len, max_len, use_heatmap=True) -> list[dict]:
    why: dict[tuple[int, int], set[str]] = {}
    for tag, times in anchors(sents, meta, loud, use_heatmap).items():
        for t in times:
            k = at(sents, t)
            for span in spans(sents, range(max(k - 3, 0), k + 1), min_len, max_len):
                why.setdefault(span, set()).add(tag)
    hooks = [i for i, p in enumerate(hook_p) if p >= HOOK_P]
    for tag, idx in (("hook", hooks), ("slide", range(0, len(sents), 4))):
        for span in spans(sents, idx, min_len, max_len):
            why.setdefault(span, set()).add(tag)
    return [{"id": f"{i}-{j}", "i": i, "j": j, "s": sents[i]["s"], "e": sents[j]["e"], "why": sorted(w)}
            for (i, j), w in sorted(why.items())]
