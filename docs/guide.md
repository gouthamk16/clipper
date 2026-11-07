# Clipper user guide

Everything beyond the quick start: how a clip gets made, every option, what to do with the
clips once you have them, and fixes for the usual problems.

- [How a clip gets made](#how-a-clip-gets-made)
- [Things to ask for](#things-to-ask-for)
- [Options](#options)
- [Posting your clips](#posting-your-clips)
- [Finding videos to clip](#finding-videos-to-clip)
- [Running it without Claude](#running-it-without-claude)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

## How a clip gets made

1. **Prepare.** The video is downloaded (or opened from disk) and transcribed word by word. Clipper also pulls the parts YouTube shows as most replayed, timestamps viewers posted in the comments, and the hashtags popular Shorts on the same topic are using. All of it goes into `transcript.txt`.
2. **Pick.** Claude reads the transcript and writes `picks.json`: where each clip starts and ends, the hook shown on screen, and the title, description and hashtags for posting.
3. **Render.** Each pick is cut, pauses are trimmed, the frame is cropped to follow whoever is speaking, captions and the hook are burned in, and the audio is levelled.

Everything is cached in `clipper-output/<video-id>/`. Asking for changes re-runs only step 3.

## Things to ask for

You don't need commands. These all work:

- `clip this podcast into 5 shorts: <link>`
- `find the moments where they argue`
- `only clips under 20 seconds`
- `make the hook on #3 more specific`
- `swap #5 for the bit about their first job`
- `keep the whole frame instead of cropping` (uses the blurred-background layout)
- `make the files small enough to upload from the browser` (keeps each under 10 MB)

## Options

Claude sets these for you when you ask. If you run the engine yourself
(`uv run --project <plugin folder> clipper <command> ...`), they are:

| Option | Default | What it does |
|---|---|---|
| `-n`, `--num` | 5 | Clips per video (for `run`), or videos to list (for `discover`) |
| `--reframe` | `auto` | `auto` crops to the speaker and falls back to blur when no face is found; `blur` always keeps the whole frame on a blurred background |
| `--font` | `Arial` | Caption font. Any font installed on your system |
| `--max-mb` | none | Caps each file's size, e.g. `9.5` |
| `--encoder` | `h264_nvenc` with an NVIDIA GPU, otherwise `libx264` | Any ffmpeg video encoder, e.g. `hevc_nvenc` for smaller files |
| `--whisper` | `auto` | Speech model. `auto` uses `large-v3` on a GPU and `small` on CPU |
| `--browser` | none | Borrow YouTube cookies from your browser (`chrome`, `firefox`, `edge`) when downloads are blocked |
| `-o`, `--out` | `clipper-output` | Where videos, transcripts and clips are kept |
| `--picks` | `picks.json` in the video's folder | A different picks file for `render` |

Engine commands: `doctor`, `prepare`, `render`, `run`, `discover`, `eval`.

## Posting your clips

Each clip has a `.txt` with a title, a description and hashtags. Some things that helped us:

- **Space them out.** Posting five Shorts within a few minutes did worse for us than spreading them over the day. Two hours apart is a reasonable start, and YouTube Studio's **Schedule** option does it for you.
- **Keep them short.** 15 to 35 seconds. Our clips that got pushed into the Shorts feed were 21 and 34 seconds.
- **Watch the first two seconds.** If the hook doesn't land, ask for a different opening line or a different moment.
- **Mind the upload limits.** YouTube caps daily uploads and doesn't publish the number; our channel hit it at 10. Instagram's API caps Reels at 90 seconds.
- **Check your numbers.** In YouTube Studio, the "Stayed to watch" figure on each Short tells you whether the hook works. As a rough guide, under 60% means most viewers swipe away early; our best clip held 70%.

## Finding videos to clip

`/clipper:find <topics>` searches YouTube for this month's most-viewed long videos on those
topics and ranks them by views per day. Edit `sources.toml` in your folder to change the search
terms, add channels, or set the minimum views, length and language.

Streams, podcasts, interviews and debates clip best: long, talky, full of reactions. Heavily
edited videos have less left to cut, and everyone else is clipping them too.

## Running it without Claude

With a [TypeSafe](https://typesafe.ai) API key, Jev can pick the clips instead:

```
export TYPESAFE_API_KEY=...            # or put it in a .env file in your folder
uv run --project <plugin folder> clipper run "<url or file>" -n 5
```

Jev scores every candidate moment for hook strength, payoff, emotion, surprise and how
relatable it is, and picks titles and hashtags from real lines and tags. It can't write new
text, so hooks are lines lifted from the clip rather than written for it.

You can also write `picks.json` by hand and run `render`. The format is in the clip skill
(`skills/clip/SKILL.md`).

## Troubleshooting

**"Sign in to confirm you're not a bot" or HTTP 403 from YouTube.** Add `--browser chrome` (or
`firefox`, `edge`) so the download uses your browser's YouTube cookies. If it keeps failing,
download the video another way and clip the file.

**`ffmpeg` not found.** Install it (see the README) and open a new terminal so it's on your PATH.

**Transcription is slow.** Without an NVIDIA GPU, Clipper uses the smaller speech model on your
CPU. An hour of audio can take a while. It only happens once per video.

**"GPU transcription failed, falling back to CPU".** Your GPU is there but the CUDA libraries
aren't. On Windows they install automatically; on Linux install cuDNN 9 and cuBLAS for CUDA 12.

**The crop cuts someone off.** Ask for the whole frame (`--reframe blur`).

**Captions use the wrong font.** Set `--font` to a font installed on your system.

## FAQ

**Is it free?** Yes, MIT licensed. Claude Code usage is billed as normal by Anthropic. Jev is
optional and paid per use by TypeSafe.

**Does my video leave my computer?** The video doesn't. Claude reads the transcript text as part
of your Claude Code session. Jev, if you use it, receives transcript text too.

**Can it guarantee viral clips?** No tool can. It finds the moments most likely to hold attention
and gives each a fair shot; the rest is your content, your audience and some luck.

**TikTok and Reels?** The clips are 9:16 and work on all three platforms.
