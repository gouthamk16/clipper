"""Cut a clip to 9:16: dead air removed, crop following the speaker, word captions, title card."""
import shutil
import subprocess
import urllib.request
from pathlib import Path

import numpy as np

ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},86,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,7,3,2,60,60,560,1
Style: Title,{font},60,&H00FFFFFF,&H00FFFFFF,&H00000000,&HC0000000,1,0,0,0,100,100,0,0,3,14,0,8,90,90,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
HIGHLIGHT = "{\\c&H00E5FF&\\fscx112\\fscy112}"
TITLE_SECS = 3
GAP = 0.7   # silences longer than this are cut out
PAD = 0.2   # kept either side of speech so words aren't clipped
YUNET = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"


def default_encoder() -> str:
    """NVENC when an NVIDIA GPU is present, otherwise the software encoder every ffmpeg build has."""
    return "h264_nvenc" if shutil.which("nvidia-smi") else "libx264"


def keep(words: list[dict], s: float, e: float) -> tuple[list[tuple[float, float]], list[dict], float]:
    """The stretches of [s, e] that contain speech, as clip-relative (start, end) pairs,
    with the words re-timed to the shortened clip and its new duration."""
    runs = []
    for w in (w for w in words if w["e"] > s and w["s"] < e):
        if runs and w["s"] - runs[-1][-1]["e"] <= GAP:
            runs[-1].append(w)
        else:
            runs.append([w])
    if not runs:
        return [(0.0, e - s)], [], e - s
    segs, timed, t, end = [], [], 0.0, s
    for run in runs:
        a, b = max(run[0]["s"] - PAD, end), min(run[-1]["e"] + PAD, e)
        timed += [{"s": w["s"] - a + t, "e": w["e"] - a + t, "w": w["w"]} for w in run]
        segs.append((a - s, b - s))
        t, end = t + b - a, b
    return segs, timed, t


def ass_time(t: float) -> str:
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def chunks(words: list[dict]) -> list[list[dict]]:
    """Caption groups of up to three words, broken at pauses and punctuation."""
    out, cur = [], []
    for w in words:
        if cur and (len(cur) == 3 or w["s"] - cur[-1]["e"] > 0.4 or cur[-1]["w"][-1] in ".!?,"):
            out.append(cur)
            cur = []
        cur.append(w)
    return out + [cur] if cur else out


def ass(words: list[dict], dur: float, title: str, font: str) -> str:
    """Subtitle file for a clip of `dur` seconds; `words` are timed from the clip's start."""
    ev = []
    if title:
        ev.append(f"Dialogue: 1,{ass_time(0)},{ass_time(TITLE_SECS)},Title,,0,0,0,,{title}")
    groups = chunks(words)
    for g, group in enumerate(groups):
        hold = min(groups[g + 1][0]["s"] if g + 1 < len(groups) else dur, group[-1]["e"] + 0.5)
        for k, w in enumerate(group):
            t1 = min(group[k + 1]["s"] if k + 1 < len(group) else hold, dur)
            line = " ".join(HIGHLIGHT + x["w"].upper() + "{\\r}" if x is w else x["w"].upper()
                            for x in group)
            ev.append(f"Dialogue: 0,{ass_time(w['s'])},{ass_time(t1)},Cap,,0,0,0,,{line}")
    return ASS_HEAD.format(font=font) + "\n".join(ev) + "\n"


def hold(picks: list[tuple[float, float]], jump: float) -> list[tuple[float, float]]:
    """Keep the crop still on one face; cut to another only once it has led for three samples."""
    steps, away = [(0.0, [picks[0][1]])], []
    for t, x in picks[1:]:
        if abs(x - np.median(steps[-1][1])) <= jump:
            steps[-1][1].append(x)
            away = []
        else:
            away.append((t, x))
            if len(away) == 3:
                steps.append((away[0][0], [a[1] for a in away]))
                away = []
    return [(t, float(np.median(xs))) for t, xs in steps]


def speaker_x(src: str, s: float, e: float) -> list[tuple[float, float]] | None:
    """Where to centre the crop over the clip, as (time, x) steps that follow whoever is
    talking. None when faces are missing or small (gameplay, wide shots)."""
    import cv2

    model = Path.home() / ".cache" / "clipper" / "yunet.onnx"
    if not model.exists():
        model.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(YUNET, model)
    cap = cv2.VideoCapture(src)
    cap.set(cv2.CAP_PROP_POS_MSEC, s * 1000)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    scale, step = 640 / width, max(round(fps / 4), 1)
    det, prev, picks, samples = None, None, [], 0
    for n in range(int((e - s) * fps)):
        ok, frame = cap.read()
        if not ok:
            break
        if n % step:
            continue
        samples += 1
        small = cv2.resize(frame, (640, int(frame.shape[0] * scale)))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        det = det or cv2.FaceDetectorYN.create(str(model), "", gray.shape[::-1], 0.7)
        faces = det.detect(small)[1]
        best = None
        for f in faces if faces is not None else []:
            x, y, w, h = f[:4]
            mx, my = (f[10] + f[12]) / 2, (f[11] + f[13]) / 2
            box = np.s_[max(int(my - h / 6), 0):int(my + h / 6), max(int(mx - w / 4), 0):int(mx + w / 4)]
            # A talking mouth changes between samples; a listener's mostly doesn't.
            moved = cv2.absdiff(gray[box], prev[box]).mean() if prev is not None and gray[box].size else 0
            if best is None or moved > best[0]:
                best = (moved, (x + w / 2) / scale, w / scale)
        prev = gray
        if best:
            picks.append((n / fps, best[1], best[2]))
    if len(picks) < samples / 2 or np.median([p[2] for p in picks]) < 0.06 * width:
        return None
    return hold([(t, x) for t, x, _ in picks], 0.1 * width)


def size(src: str) -> tuple[int, int]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "csv=p=0", src],
                         capture_output=True, text=True, check=True).stdout
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


def render(src: str, clip: dict, words: list[dict], out: Path, reframe: str, font: str, enc: str,
           max_mb: float | None = None) -> Path:
    s, e = clip["s"], clip["e"]
    w, h = size(src)
    segs, timed, dur = keep(words, s, e)
    sub = out.with_suffix(".ass")
    sub.write_text(ass(timed, dur, clip["title"], font), encoding="utf-8")
    spoken = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in segs)
    cut = f"select='{spoken}',setpts=N/FRAME_RATE/TB"
    # ffmpeg runs in the output folder so the subtitle path has no drive colon,
    # which the filter syntax would read as an option separator.
    cap = f"ass={sub.name}"
    fill = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    vertical = w / h <= 9 / 16 + 0.01
    steps = None if vertical or reframe == "blur" else speaker_x(src, s, e)
    if vertical:
        vf = f"{cut},{fill},{cap}"
    elif steps:
        cw = int(h * 9 / 16) // 2 * 2
        xs = [int(min(max(x - cw / 2, 0), w - cw)) for _, x in steps]
        x = str(xs[-1])
        for (t, _), left in zip(reversed(steps[1:]), reversed(xs[:-1])):
            x = f"if(lt(t,{t:.3f}),{left},{x})"
        # crop before the cut, while t is still the clip's original timeline
        vf = f"crop={cw}:{h}:'{x}':0,{cut},scale=1080:1920,{cap}"
    else:
        vf = (f"{cut},split[a][b];[a]{fill},boxblur=25:2,eq=brightness=-0.08[bg];"
              f"[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,{cap}")
    quality = ["-preset", "p5", "-cq", "23"] if enc.endswith("nvenc") else ["-preset", "medium", "-crf", "20"]
    if max_mb:
        # A bitrate ceiling instead of constant quality, so the file fits an upload limit.
        rate = int(max_mb * 8e6 * 0.93 / dur) - 160_000
        quality = ["-preset", "p5" if enc.endswith("nvenc") else "medium",
                   "-b:v", str(rate), "-maxrate", str(rate), "-bufsize", str(2 * rate)]
    if "hevc" in enc or "265" in enc:
        quality += ["-tag:v", "hvc1"]
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", src,
                        "-filter_complex", vf,
                        "-af", f"aselect='{spoken}',asetpts=N/SR/TB,loudnorm=I=-14:TP=-1.5:LRA=11",
                        "-c:v", enc, *quality, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                        "-movflags", "+faststart", out.name],
                       cwd=out.parent, check=True)
    finally:
        sub.unlink()
    return out
