"""What is in the video: words with timestamps, and loudness."""
import os
import re
import subprocess
import sysconfig
from pathlib import Path

import numpy as np

SR = 16000
HOP = 0.5


def audio(path: str) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def transcribe(a: np.ndarray, model: str) -> list[dict]:
    # ctranslate2 loads cuBLAS/cuDNN by name, and pip installs them where Windows doesn't look.
    for d in Path(sysconfig.get_paths()["purelib"]).glob("nvidia/*/bin"):
        os.environ["PATH"] = f"{d}{os.pathsep}{os.environ['PATH']}"
    import ctranslate2
    from faster_whisper import BatchedInferencePipeline, WhisperModel

    def run(device: str, name: str) -> list[dict]:
        segs, _ = BatchedInferencePipeline(WhisperModel(name, device=device, compute_type="auto")).transcribe(
            a, word_timestamps=True, batch_size=8)
        return [{"s": w.start, "e": w.end, "w": w.word.strip()}
                for seg in segs for w in seg.words or [] if w.word.strip()]

    # large-v3 on CPU runs slower than real time; small is the usable trade-off there.
    cpu_model = "small" if model == "auto" else model
    if not ctranslate2.get_cuda_device_count():
        return run("cpu", cpu_model)
    try:
        return run("cuda", "large-v3" if model == "auto" else model)
    except RuntimeError as err:  # a GPU whose CUDA libraries (cuBLAS, cuDNN) aren't installed
        print(f"GPU transcription failed ({err}); falling back to CPU")
        return run("cpu", cpu_model)


def sentences(words: list[dict]) -> list[dict]:
    sents, cur = [], []
    for k, w in enumerate(words):
        cur.append(w)
        pause = k + 1 < len(words) and words[k + 1]["s"] - w["e"] > 0.8
        if re.search(r"[.!?]$", w["w"]) or pause or len(cur) >= 40:
            sents.append(cur)
            cur = []
    if cur:
        sents.append(cur)
    return [{"s": c[0]["s"], "e": c[-1]["e"], "text": " ".join(x["w"] for x in c)} for c in sents]


def loudness(a: np.ndarray) -> list[float]:
    """Loudness per HOP seconds, z-scored against the whole video."""
    n = int(SR * HOP)
    frames = a[: len(a) // n * n].reshape(-1, n)
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(1)) + 1e-6)
    return ((db - db.mean()) / (db.std() + 1e-6)).round(3).tolist()

