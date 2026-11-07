"""Policy: which judged candidates are kept, and in what order."""
import math

from clipper.perceive import HOP

# Hand-set until posted clips give us view counts to learn these from.
WEIGHTS = {"hook": 0.30, "payoff": 0.15, "emotion": 0.15, "surprise": 0.15,
           "relatable": 0.10, "replay": 0.10, "energy": 0.05}
REJECT_ABOVE = {"mid_thought": 0.6, "needs_context": 0.6, "sponsor": 0.5}
COMPLETE_MIN = 0.4


def signals(c: dict, heatmap: list[dict], loud: list[float]) -> dict:
    """Non-language features on the same 0-1 scale as Jev's scores."""
    seg = loud[int(c["s"] / HOP):int(c["e"] / HOP) + 1]
    out = {"energy": 1 / (1 + math.exp(-sum(seg) / len(seg)))}
    hot = [h["value"] for h in heatmap if h["start_time"] < c["e"] and h["end_time"] > c["s"]]
    if hot:
        out["replay"] = sum(hot) / len(hot)
    return out


def total(f: dict) -> float:
    """Weighted mean over the features present, so a video with no heatmap isn't penalised."""
    used = [k for k in WEIGHTS if k in f]
    return sum(WEIGHTS[k] * f[k] for k in used) / sum(WEIGHTS[k] for k in used)


def rank(cands: list[dict], n: int) -> list[dict]:
    """Top n candidates that pass the gates and don't overlap in time. Each needs `f`."""
    ok = [c for c in cands
          if all(c["f"][k] <= cap for k, cap in REJECT_ABOVE.items()) and c["f"]["complete"] >= COMPLETE_MIN]
    chosen = []
    for c in sorted(ok, key=lambda c: -total(c["f"])):
        if all(c["e"] <= o["s"] or c["s"] >= o["e"] for o in chosen):
            chosen.append(c | {"score": round(100 * total(c["f"]))})
            if len(chosen) == n:
                break
    return chosen
