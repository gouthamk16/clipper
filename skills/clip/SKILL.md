---
name: clip
description: Turn a long video, podcast, stream or interview into vertical Shorts, Reels or TikToks with word-by-word captions, an on-screen hook, and a ready-to-post title, description and hashtags. Use when someone wants clips, shorts, reels, highlights or "the best moments" cut from a YouTube link or a video file.
when_to_use: 'Requests like: clip this video, make shorts from my podcast, find the best moments in this stream, cut 5 reels from this, turn this into TikToks.'
argument-hint: '<youtube-url-or-file> [number of clips]'
allowed-tools: Bash(uv run --project *) Read Write Edit
---

# Clip a long video into Shorts

You are the editor. The `clipper` engine downloads, transcribes, reframes, captions and
renders. You read the transcript, choose the moments, and write the words people see.

Run every engine command from the user's current folder, so their clips land in
`./clipper-output/`:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}" clipper <command> ...
```

## 1. Check the setup (first time only)

Run `uv run --project "${CLAUDE_PLUGIN_ROOT}" clipper doctor`.

- If `uv` isn't found, tell the user to install it (one line, from https://docs.astral.sh/uv/getting-started/installation/) and stop.
- If ffmpeg is missing, tell them how to install it for their OS (`winget install ffmpeg`, `brew install ffmpeg`, `sudo apt install ffmpeg`) and stop.
- The first run installs the engine's Python packages. That can take a few minutes; say so.
- No GPU is fine. Transcription is slower on CPU, nothing else changes.

## 2. Prepare the transcript

```
uv run --project "${CLAUDE_PLUGIN_ROOT}" clipper prepare "<url or file>"
```

It prints the path of `transcript.txt` and of the `picks.json` you will write. A one-hour
video takes a few minutes on a GPU; tell the user it's working.

If the user set `TYPESAFE_API_KEY` and wants it fully automatic, `clipper run "<url or file>" -n <count>`
picks and renders without you. Otherwise continue.

## 3. Choose the moments

Read `transcript.txt`. For long videos read it in chunks; don't skip parts. Each line is
`[index] start-end (signals) text`. Signals mark where the audience already reacted:
`replayed` (YouTube's most-replayed parts), `comments` (viewers posted that timestamp),
`loud` (an energy spike). Treat them as leads, not answers. Judge the words.

Pick the number of clips the user asked for (default 5). A good clip:

- **Opens on the hook.** The first sentence must work with zero context: a bold claim, a
  question, a confession, a number, a conflict. Never start on "So", "And", "Yeah", "But", or
  a reference to something said earlier ("that thing", "he said").
- **Stands alone.** Someone scrolling past knows what's going on without the rest of the video.
- **Pays off.** It ends on a punchline, a reveal, a conclusion or a strong reaction, not mid-thought.
- **Is short.** 15-35 seconds; 20-30 is the sweet spot. Shorter beats longer when in doubt.
- **Has energy.** Laughter, disagreement, surprise and strong opinions outperform explanation.
- **Isn't filler.** Skip intros, sponsor reads, "like and subscribe", and housekeeping.
- **Doesn't overlap** another pick.

## 4. Write the words

For each pick write:

- `hook`: the on-screen text for the first 3 seconds. 3-7 words. Specific beats vague: "He
  turned down $1M on stream" beats "You won't believe this". Promise only what the clip delivers.
- `title`: the post title, under 60 characters, strongest words first. A question or a direct
  claim. No ALL CAPS, no emoji walls.
- `description`: one or two plain sentences that add context or ask a question viewers will
  want to answer in the comments.
- `hashtags`: 3-5 that a real viewer would search. Use relevant ones from the transcript
  header's "hashtags on popular Shorts" line when they fit. Never more than 15 in total.

Write like a person talking to a friend. No "delve", "unlock", "game-changer", "in today's
world", or "not just X, but Y". Match the energy of the source: a gaming stream and a finance
podcast don't sound alike.

Save the list to the `picks.json` path that `prepare` printed:

```json
[
  {
    "start": 42, "end": 47,
    "hook": "He turned down $1M on stream",
    "title": "Why he said no to a million dollars",
    "description": "Would you have taken it?",
    "hashtags": ["#podcast", "#money", "#interview"]
  }
]
```

`start` and `end` are transcript line indices, inclusive. The engine trims dead air, so pick
whole sentences and don't worry about pauses.

## 5. Render

```
uv run --project "${CLAUDE_PLUGIN_ROOT}" clipper render "<same url or file>"
```

Useful options: `--reframe blur` keeps the whole frame on a blurred background instead of
cropping to the speaker; `--max-mb 9.5` keeps files under 10 MB; `--font "Arial"` changes the
caption font.

## 6. Hand it over

Show a short table: number, length, hook, title. Give the folder path. Each `NN.mp4` has an
`NN.txt` beside it with the title, description and hashtags ready to paste.

Then offer edits in plain terms ("make #2 shorter", "punchier hook on #4", "swap #5 for the
part about X"). To apply one, edit `picks.json` and run `render` again. Nothing is re-downloaded
or re-transcribed.

## Using other people's videos

If the source isn't the user's own and they haven't mentioned permission, say once, briefly:
reposting someone else's content can get claims or takedowns, and YouTube gives less reach to
channels that mostly re-upload other creators' clips. Clipping programs where creators pay for
clips are the safe way to do it. Then do what they asked; don't repeat the warning.
