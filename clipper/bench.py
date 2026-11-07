"""Grade the ranker against YouTube's most-replayed data, which it was not shown.

Replay intensity is the only free label for "viewers cared about this moment". It is
a proxy: it also rises wherever people seek to, which is why the benchmark set has no
chapters and why `position` is reported as the baseline to beat."""
import numpy as np

from clipper.rank import rank, signals, total


def spearman(x, y) -> float:
    rx, ry = (np.argsort(np.argsort(v)) for v in (x, y))
    return float(np.corrcoef(rx, ry)[0, 1])


def grade(cands: list[dict], heat: list[dict], loud: list[float], n: int) -> dict:
    """One video. `cands` are judged without replay; returns top-n results and per-feature rho."""
    replay = np.array([signals(c, heat, loud)["replay"] for c in cands])
    peak = np.array([max(h["value"] for h in heat if h["start_time"] < c["e"] and h["end_time"] > c["s"])
                     for c in cands])
    hot = np.quantile([h["value"] for h in heat[1:]], 0.9)
    idx = {c["id"]: k for k, c in enumerate(cands)}
    picks = [idx[c["id"]] for c in rank(cands, n)]
    cols = {k: [c["f"][k] for c in cands] for k in cands[0]["f"]}
    cols |= {"total": [total(c["f"]) for c in cands], "position": [-c["s"] for c in cands]}
    return {
        "lift": float(replay[picks].mean() / replay.mean()),
        "hit": float((peak[picks] >= hot).mean()),
        "chance": float((peak >= hot).mean()),
        "rho": {k: spearman(v, replay) for k, v in cols.items()},
    }


def report(grades: list[dict]) -> str:
    lifts = np.array([g["lift"] for g in grades])
    lines = [
        f"videos: {len(grades)}",
        f"top-pick replay lift: mean {lifts.mean():.2f}x, median {np.median(lifts):.2f}x, "
        f"above 1.0 in {(lifts > 1).sum()}/{len(lifts)}",
        f"picks on a top-10% replay segment: {np.mean([g['hit'] for g in grades]):.0%} "
        f"(any candidate: {np.mean([g['chance'] for g in grades]):.0%})",
        "rank correlation with replay, mean over videos (videos where positive):",
    ]
    rho = {k: np.array([g["rho"][k] for g in grades]) for k in grades[0]["rho"]}
    for k, v in sorted(rho.items(), key=lambda kv: -kv[1].mean()):
        lines.append(f"  {k:14} {v.mean():+.3f}  ({(v > 0).sum()}/{len(v)})")
    return "\n".join(lines)
