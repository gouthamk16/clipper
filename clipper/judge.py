"""Jev's judgments. Jev answers typed questions and writes no text, so code proposes
every candidate and every option, and Jev only scores or selects."""
import asyncio
import re

from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, Score, TypeSafeError

USD_PER_M = 0.042  # input tokens; output is free

HOOK = Noul(instructions="Would `line`, heard with no context as the first words of a short "
                         "video, make a stranger stop scrolling to hear what comes next?")

# Score levels describe situations, not degrees: Jev reads each level on its own.
SCORES = {
    "hook": Score(
        instructions="`opening_line` is the first thing a stranger hears in a short video. "
                     "How strongly does it make them keep watching?",
        criteria=["Filler, a greeting, or the tail of an earlier point; means nothing on its own",
                  "States a topic plainly, with no tension or curiosity",
                  "Raises a clear question, stake or promise the viewer wants resolved",
                  "A startling claim, confession, conflict or number that demands an explanation"]),
    "payoff": Score(
        instructions="How does `clip` end?",
        criteria=["Stops in the middle of an idea with nothing resolved",
                  "Trails off or drifts to a new topic",
                  "Finishes the idea it started",
                  "Lands a punchline, reveal or memorable conclusion that pays off its opening"]),
    "emotion": Score(
        instructions="How much feeling is in `clip`?",
        criteria=["Flat, procedural or administrative talk",
                  "Mild interest or a measured opinion",
                  "Clear feeling: excitement, anger, humour or vulnerability",
                  "Intense: an outburst, a confession, a heated disagreement or a big laugh"]),
    "surprise": Score(
        instructions="How unexpected is what `clip` says?",
        criteria=["Common knowledge or routine detail",
                  "Useful but expected",
                  "A counterintuitive point or an unusual story",
                  "A claim most people would find shocking or want to argue with"]),
    "relatable": Score(
        instructions="Who would care about `clip`?",
        criteria=["Only insiders of a niche, or people who watched the whole video",
                  "People in one hobby or profession",
                  "Most adults: it touches money, work, relationships, health or status",
                  "Almost anyone would see their own life in it"]),
}
TOP = 3
NOULS = {
    "mid_thought": Noul(instructions="Does `opening_line` depend on something said in `before` to "
                                     "make sense, such as continuing a sentence or referring to an "
                                     "unnamed person or thing?"),
    "needs_context": Noul(instructions="Would a viewer who sees only `clip`, and nothing before it, "
                                       "be confused about what is being discussed?"),
    "complete": Noul(instructions="Does `clip` end on a finished thought?"),
    "sponsor": Noul(instructions="Is `clip` mainly an advertisement, a sponsor read, a request to "
                                 "like or subscribe, or an intro or outro?"),
}
FIRST = ("A short video is being cut from `passage`. Which line is the strongest first line: "
         "it makes sense with nothing before it and makes a stranger want to hear what comes next?")
LAST = ("A short video is being cut from `passage`. Which line is the strongest last line: "
        "it finishes the thought and leaves nothing hanging?")
# Offered alongside the source video's own tags and channel name.
POOL = ["podcast", "interview", "motivation", "comedy", "funny", "politics", "news", "tech", "gaming",
        "sports", "business", "money", "storytime", "debate", "speech", "advice", "celebrity", "science",
        "history", "relationships"]
TAGS = 8   # YouTube ignores every hashtag on a video that has more than 15
TITLE = ("Which line from `passage` works best as an on-screen headline for the video: "
         "short, quotable, and intriguing without giving away the ending?")


def ask(jobs: list[tuple[dict, dict]]) -> list:
    """One Jev request per (state, questions). A failed request yields None, never a guess."""
    async def run():
        sem = asyncio.Semaphore(16)
        async with AsyncTypeSafeClient() as client:
            async def one(state, questions):
                async with sem:
                    try:
                        return await client.system_one(state, questions)
                    except TypeSafeError as err:
                        print(f"jev request failed: {err}")
            return await asyncio.gather(*(one(s, q) for s, q in jobs))

    res = asyncio.run(run())
    tokens = sum(r.usage.input_tokens for r in res if r)
    print(f"jev: {len(jobs)} requests, {tokens:,} tokens, ${tokens * USD_PER_M / 1e6:.4f}")
    return res


def text(sents: list[dict], i: int, j: int) -> str:
    return " ".join(s["text"] for s in sents[max(i, 0):j + 1])


def hooks(sents: list[dict], title: str) -> list[float]:
    """Per sentence, the probability it works as an opening line."""
    res = ask([({"video_title": title, "line": s["text"]}, {"hook": HOOK}) for s in sents])
    return [r.nouls["hook"].noul if r else 0.0 for r in res]


def score(cands: list[dict], sents: list[dict], title: str) -> list[dict | None]:
    """Per candidate, every Score normalised to 0-1 and every Noul probability."""
    jobs = [({"video_title": title,
              "before": text(sents, c["i"] - 2, c["i"] - 1),
              "opening_line": sents[c["i"]]["text"],
              "clip": text(sents, c["i"], c["j"])}, SCORES | NOULS) for c in cands]
    return [r and ({k: r.scores[k].score / TOP for k in SCORES} | {k: r.nouls[k].noul for k in NOULS})
            for r in ask(jobs)]


def refine(clips: list[dict], sents: list[dict], title: str) -> None:
    """Trim each clip's start and end to the best nearby sentence, and pick its title line."""
    plans = []
    for c in clips:
        i, j = c["i"], c["j"]
        # Only inward: earlier starts and later ends were already judged as their own
        # candidates, and growing a clip could overlap its neighbour or pass the length cap.
        first = [k for k in range(i, i + 3) if k < j] or [i]
        last = [k for k in range(j - 2, j + 1) if k > first[-1]]
        lines = [k for k in range(i, j + 1) if 3 <= len(sents[k]["text"].split()) <= 14]
        asks = {"i": (FIRST, first), "j": (LAST, last), "title": (TITLE, lines)}
        qs = {name: Choice(instructions=ins, criteria={str(k): sents[k]["text"] for k in opts})
              for name, (ins, opts) in asks.items() if len(opts) > 1}
        plans.append(({"video_title": title, "passage": text(sents, i, j)}, qs))
    for c, (_, qs), r in zip(clips, plans, ask(plans)):
        picked = {name: int(r.choices[name].choice) for name in qs} if r else {}
        c["i"], c["j"] = picked.get("i", c["i"]), picked.get("j", c["j"])
        c["s"], c["e"] = sents[c["i"]]["s"], sents[c["j"]]["e"]
        c["title"] = sents[picked["title"]]["text"] if "title" in picked else ""


def hashtags(clips: list[dict], sents: list[dict], meta: dict, trend: dict[str, float]) -> None:
    """Pick each clip's hashtags. Candidates are what current popular Shorts on the topic use
    (`trend`), the source video's tags, its channel and a general pool; Jev keeps the ones that
    fit the clip, and the most-used come first."""
    own = [re.sub(r"\W", "", t).lower() for t in [*meta.get("tags", []), meta.get("channel", "")]]
    hot = sorted(trend, key=lambda t: -trend[t])
    pool = list(dict.fromkeys(t for t in hot + own + POOL if 2 < len(t) <= 30 and t != "shorts"))[:60]
    jobs = [({"video_title": meta["title"], "clip": text(sents, c["i"], c["j"])},
             {t: Noul(instructions=f"Would a viewer browsing the hashtag #{t} be glad to find `clip`?")
              for t in pool}) for c in clips]
    for c, r in zip(clips, ask(jobs)):
        fit = [t for t in pool if r and r.nouls[t].noul >= 0.5]
        c["tags"] = sorted(fit, key=lambda t: (-trend.get(t, 0), -r.nouls[t].noul))[:TAGS]
