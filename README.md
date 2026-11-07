<p align="center">
  <img src="assets/demo.gif" width="260" alt="A vertical clip made by Clipper: hook text on top, word-by-word captions below">
</p>

<p align="center"><a href="assets/demo.mp4">Watch the 30-second demo</a></p>

<h1 align="center">Clipper</h1>

<p align="center"><b>Paste a long video into Claude Code. Get Shorts back.</b><br>
Claude watches the whole thing, picks the moments worth posting, writes the hooks,<br>
and your own computer cuts them into vertical clips with captions.</p>

---

You recorded a two-hour podcast. Somewhere in there are five moments that would do well
as Shorts. Finding them means scrubbing through the whole thing, cutting, reframing,
captioning, and then staring at a blank title box.

Clipper does that part. You type one line:

```
/clipper:clip https://youtube.com/watch?v=... 5
```

and a few minutes later you have five vertical clips, each with:

- **The moment, cut clean.** Claude reads the full transcript and chooses clips that open on a hook, make sense on their own, and land a payoff.
- **A hook on screen.** A short line in the first three seconds, written for the person scrolling past.
- **Word-by-word captions** that light up as each word is spoken.
- **A crop that follows whoever is talking**, so two-person podcasts don't end up showing an empty chair.
- **Dead air removed.** Pauses longer than 0.7 seconds are cut out.
- **A posting file** next to each clip with a title, description and hashtags, ready to paste into YouTube, Instagram or TikTok.

It runs on your machine. No uploads to a clipping service, no watermark, no per-minute credits.

## Install

You need [Claude Code](https://code.claude.com), [uv](https://docs.astral.sh/uv/getting-started/installation/) and [ffmpeg](https://ffmpeg.org/download.html).

```
# ffmpeg: pick your system
winget install ffmpeg          # Windows
brew install ffmpeg            # macOS
sudo apt install ffmpeg        # Ubuntu / Debian
```

Then, inside Claude Code:

```
/plugin marketplace add gouthamk16/clipper
/plugin install clipper@clipper
```

The first clip takes a few extra minutes while the engine installs its Python packages and
downloads the speech model. After that it starts straight away.

## Use it

Talk to it like you'd talk to an editor:

```
/clipper:clip my-podcast-episode-12.mp4
/clipper:clip https://youtube.com/watch?v=... 3
clip the three funniest moments from this stream: <link>
make #2 shorter and give #4 a punchier hook
```

Edits are quick: Claude changes the pick and re-renders. Nothing is downloaded or transcribed twice.

Looking for something to clip?

```
/clipper:find gaming streams, tech podcasts
```

lists this month's fastest-growing long videos on those topics, ranked by views per day.

## What you get

```
clipper-output/<video-id>/clips/
├── 01.mp4      vertical 1080x1920, captions burned in
├── 01.txt      title, description, hashtags
├── 02.mp4
├── 02.txt
└── clips.json  every clip's timing and text
```

## How it picks moments

Claude reads every sentence of the transcript. Lines are tagged with what the audience already
told us: the parts YouTube shows as **most replayed**, timestamps that **viewers posted in the
comments**, and **energy spikes** in the audio. Those are leads. The choice comes down to whether
a clip hooks in the first second, stands on its own, and ends on something.

## What we learned posting with it

We used Clipper on a real channel before releasing it. Two things stood out:

- **Shorter won.** The clips that got pushed into the Shorts feed were 21 and 34 seconds long. Nothing over 38 seconds got any reach, so Clipper aims for 15 to 35.
- **Reposting other people's clips is getting harder.** Since 1 October 2026, YouTube gives less reach to channels that mostly re-upload other creators' videos. Clips from your own content, or from creators who pay or invite clippers, are the way to go.

## Requirements

| | |
|---|---|
| OS | Tested on Windows. macOS and Linux should work but haven't been tested yet; reports welcome |
| GPU | Optional. An NVIDIA GPU makes transcription about 20x real time; on CPU a smaller speech model is used and it takes longer |
| Disk | About 3 GB for the speech model and packages |
| Sources | YouTube links or any local video file ffmpeg can read |

Run `uv run --project <plugin folder> clipper doctor`, or just ask Claude to check your setup.

## Optional: Jev

If you have a [TypeSafe](https://typesafe.ai) API key, set `TYPESAFE_API_KEY` and Clipper can pick and
render clips without Claude, scoring every candidate with Jev. It's fast and cheap (a few cents
for an hour of video). Without a key, Claude does the picking.

## Use it responsibly

Clip what you own, or what you have permission to clip. Reposting someone else's video can get
copyright claims or takedowns, and the platforms treat plain re-uploads as low value. Clipping
programs, where creators pay clippers per view, are the legitimate way to clip other people's content.

## More

- [User guide](docs/guide.md): every option, posting tips, troubleshooting
- Issues and ideas: [GitHub issues](https://github.com/gouthamk16/clipper/issues)

MIT licensed.
