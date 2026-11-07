"""Long video in, vertical Shorts out. Each clip gets a .txt beside it with the title,
description and hashtags to post.

clipper doctor                   check ffmpeg, GPU and keys
clipper prepare <url|file>       download, transcribe and write transcript.txt for picking clips
clipper render <url|file>        cut the clips listed in picks.json (written by you or Claude)
clipper run <url|file>...        pick and cut clips automatically with Jev (needs TYPESAFE_API_KEY)
clipper discover                 list fast-growing videos from sources.toml into queue.txt
clipper eval bench/videos.txt    grade the Jev ranker against YouTube's most-replayed data

A source ending in .txt is read as one source per line; text after # is ignored."""
import argparse
import json
import os
import shutil
import sys
import tomllib
from pathlib import Path

from yt_dlp.utils import DownloadError

from clipper import bench, handoff, judge
from clipper.discover import discover, trending_tags
from clipper.ingest import ingest
from clipper.perceive import audio, loudness, sentences, transcribe
from clipper.propose import anchors, propose
from clipper.rank import rank, signals
from clipper.render import default_encoder, render


def cached(path: Path, make):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    val = make()
    path.write_text(json.dumps(val), encoding="utf-8")
    return val


def hear(a, source: str, video: bool = True):
    """Download (or open) the video and transcribe it, cached in its work dir."""
    work = ingest(source, Path(a.out), a.browser, video=video)
    meta = json.loads((work / "meta.json").read_text(encoding="utf-8"))

    def listen():
        pcm = audio(meta["path"])
        return {"words": transcribe(pcm, a.whisper), "loud": loudness(pcm)}

    heard = cached(work / "heard.json", listen)
    return work, meta, heard["words"], heard["loud"]


def candidates(a, source: str, blind: bool = False):
    """Every stage up to ranking, each cached in the video's work dir.
    `blind` hides the most-replayed data from every stage and skips the video download."""
    work, meta, words, loud = hear(a, source, video=not blind)
    title = meta["title"]
    sents = sentences(words)
    hook_p = cached(work / "hooks.json", lambda: judge.hooks(sents, title))
    lo, hi = a.min, a.max
    if sents[-1]["e"] < hi * 1.5:  # short source: shrink the window to fit
        hi = max(min(hi, sents[-1]["e"] * 0.45), 6)
        lo = min(lo, hi * 0.5)
    cands = propose(sents, meta, loud, hook_p, lo, hi, use_heatmap=not blind)

    answers = work / "answers.json"
    seen = json.loads(answers.read_text(encoding="utf-8")) if answers.exists() else {}
    todo = [c for c in cands if c["id"] not in seen]
    if todo:
        for c, ans in zip(todo, judge.score(todo, sents, title)):
            if ans:
                seen[c["id"]] = ans
        answers.write_text(json.dumps(seen), encoding="utf-8")
    heat = [] if blind else meta.get("heatmap", [])
    judged = [c | {"f": seen[c["id"]] | signals(c, heat, loud)} for c in cands if c["id"] in seen]
    print(f"{meta['title'][:50]}: {len(sents)} sentences, {len(judged)} judged candidates")
    return work, meta, words, sents, loud, judged


def posting(c: dict, meta: dict) -> str:
    """What to paste into YouTube when posting the clip. Titles are capped at 100 characters."""
    title = c.get("post_title") or c["title"] or meta["title"]
    source = [f"From: {meta['title']}", *filter(None, [meta.get("channel"), meta.get("url")])]
    tags = " ".join(f"#{t}" for t in dict.fromkeys([*c["tags"], "shorts"]))
    return "\n".join(["TITLE", f"{title[:91]} #shorts", "", "DESCRIPTION", c.get("description") or title, "",
                      *source, "", tags, ""])


def save(a, work: Path, meta: dict, words: list[dict], clips: list[dict], name) -> Path:
    """Render every clip into work/clips with its posting file, and list them in clips.json."""
    out = work / "clips"
    out.mkdir(exist_ok=True)
    for k, c in enumerate(clips, 1):
        c["file"] = render(meta["path"], c, words, out / f"{name(k, c)}.mp4",
                           a.reframe, a.font, a.encoder, a.max_mb).name
        (out / c["file"]).with_suffix(".txt").write_text(posting(c, meta), encoding="utf-8")
        print(f"#{k} {c['s']:7.1f}-{c['e']:7.1f}s  {c['file']:18} {c['title'][:60]}")
    (out / "clips.json").write_text(json.dumps(clips, indent=2), encoding="utf-8")
    return out


def prepare(a, source: str):
    work, meta, words, loud = hear(a, source)
    sents = sentences(words)
    trend = cached(work / "trending.json", lambda: trending_tags([meta["title"]]))
    path = work / "transcript.txt"
    path.write_text(handoff.transcript(sents, anchors(sents, meta, loud), meta, trend), encoding="utf-8")
    print(f"{meta['title']}: {len(sents)} sentences")
    print(f"transcript: {path.resolve()}")
    print(f"write picks to: {(work / 'picks.json').resolve()}")


def render_picks(a, source: str):
    work, meta, words, _ = hear(a, source)
    picks = json.loads(Path(a.picks or work / "picks.json").read_text(encoding="utf-8"))
    clips = handoff.clips(picks, sentences(words))
    print(f"done -> {save(a, work, meta, words, clips, lambda k, c: f'{k:02d}').resolve()}")


def run(a, source: str):
    if not os.environ.get("TYPESAFE_API_KEY"):
        raise SystemExit("clipper run needs TYPESAFE_API_KEY for Jev. Without it, use `clipper prepare`, "
                         "pick clips in picks.json (or ask Claude to), then `clipper render`.")
    work, meta, words, sents, _, cands = candidates(a, source)
    clips = rank(cands, a.num)
    judge.refine(clips, sents, meta["title"])
    # Title only: searching a short channel name ("Karl") pulls in unrelated people.
    trend = cached(work / "trending.json", lambda: trending_tags([meta["title"]]))
    judge.hashtags(clips, sents, meta, trend)
    out = save(a, work, meta, words, clips, lambda k, c: f"{k:02d}_score{c['score']}")
    print(f"done -> {out.resolve()}")


def doctor(a):
    import ctranslate2
    import yt_dlp

    ok = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
    gpus = ctranslate2.get_cuda_device_count()
    runtime = shutil.which("node") or shutil.which("deno")
    key = bool(os.environ.get("TYPESAFE_API_KEY"))
    checks = [
        ("ffmpeg + ffprobe", ok, shutil.which("ffmpeg") or "not found: install ffmpeg and put it on PATH"),
        ("GPU for transcription", gpus > 0, "CUDA GPU found" if gpus else "none: CPU works, just slower"),
        ("video encoder", True, default_encoder()),
        ("JavaScript runtime for YouTube", bool(runtime),
         runtime or "none: install Node.js or Deno if YouTube downloads fail"),
        ("yt-dlp", True, yt_dlp.version.__version__),
        ("Jev (optional)", key, "TYPESAFE_API_KEY set" if key else "not set: Claude picks the clips instead"),
    ]
    for name, good, note in checks:
        print(f"{'ok  ' if good else 'warn'}  {name:32} {note}")
    if not ok:
        raise SystemExit(1)


def find(a):
    root = Path(a.out)
    index = root / "index.json"
    seen = set(json.loads(index.read_text(encoding="utf-8")).values()) if index.exists() else set()
    videos = discover(tomllib.loads(Path(a.sources).read_text(encoding="utf-8")), seen, a.num)
    for v in videos:
        print(f"{v['per_day']:>10,.0f} views/day  {v['views']:>12,} views  {v['days']:>5}d  {v['channel'][:20]:20} {v['title'][:60]}")
    root.mkdir(exist_ok=True)
    (root / "queue.txt").write_text("\n".join(f"{v['url']}  # {v['title']}" for v in videos), encoding="utf-8")
    print(f"queued -> {root / 'queue.txt'}")


def evaluate(a):
    grades = []
    for source in a.source:
        try:
            _, meta, _, _, loud, cands = candidates(a, source, blind=True)
        except DownloadError as err:
            print(f"skipped {source}: {err}")
            continue
        if not meta.get("heatmap") or len(cands) < 4 * a.num:
            print(f"skipped {source}: no most-replayed data, or too few candidates")
            continue
        grades.append(bench.grade(cands, meta["heatmap"], loud, a.num))
        print(f"  lift {grades[-1]['lift']:.2f}x, rho {grades[-1]['rho']['total']:+.2f}")
    if grades:
        print(bench.report(grades))


def main():
    sys.stdout.reconfigure(errors="replace")  # video titles carry emoji the Windows console can't print
    env = Path(".env")
    if env.exists():
        for line in env.read_text().splitlines():
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["doctor", "prepare", "render", "run", "discover", "eval"])
    ap.add_argument("source", nargs="*", help="video URL, local video file, or .txt list of either")
    ap.add_argument("-n", "--num", type=int, default=5, help="clips per video, or videos to discover")
    # Our Shorts that got feed distribution ran 21-34s; the 38-55s ones got none.
    ap.add_argument("--min", type=float, default=12, help="min clip length (s)")
    ap.add_argument("--max", type=float, default=35, help="max clip length (s)")
    ap.add_argument("--reframe", choices=["auto", "blur"], default="auto",
                    help="auto: crop that follows the speaker, or blur when no face is found; "
                         "blur: whole frame on a blurred background")
    ap.add_argument("--whisper", default="auto", help="Whisper model; auto is large-v3 on a GPU, small on CPU")
    ap.add_argument("--font", default="Arial")
    ap.add_argument("--encoder", default=default_encoder(), help="ffmpeg video encoder")
    ap.add_argument("--max-mb", type=float, help="cap each clip's file size, e.g. 9.5 for a 10 MB upload limit")
    ap.add_argument("--browser", help="take YouTube cookies from this browser if downloads are blocked")
    ap.add_argument("--picks", help="render: picks file (default: picks.json in the video's work dir)")
    ap.add_argument("--sources", default="sources.toml", help="discover: searches and channels to look through")
    ap.add_argument("-o", "--out", default="clipper-output", help="where videos, transcripts and clips are kept")
    a = ap.parse_args()
    a.source = [line.split("#")[0].strip() for src in a.source
                for line in (Path(src).read_text(encoding="utf-8").splitlines() if src.endswith(".txt") else [src])
                if line.split("#")[0].strip()]
    per_source = {"prepare": prepare, "render": render_picks, "run": run}
    if a.cmd in per_source:
        if not a.source:
            ap.error(f"{a.cmd} needs a video URL or file")
        for source in a.source:
            per_source[a.cmd](a, source)
    else:
        {"doctor": doctor, "discover": find, "eval": evaluate}[a.cmd](a)


if __name__ == "__main__":
    main()
