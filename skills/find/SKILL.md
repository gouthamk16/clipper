---
name: find
description: Find long videos worth clipping right now - this month's fastest-growing streams, podcasts, interviews, speeches and events on YouTube, ranked by views per day. Use when someone asks what to clip next, what's trending, or for viral videos to turn into Shorts.
when_to_use: 'Requests like: what should I clip, find trending videos, what is blowing up on YouTube, find me streams to clip.'
argument-hint: '[topics or channels]'
allowed-tools: Bash(uv run --project *) Read Write Edit
---

# Find videos to clip

1. Look for `sources.toml` in the user's current folder. If it's missing, copy
   `${CLAUDE_PLUGIN_ROOT}/sources.toml` there.
2. If the user named topics, creators or channels, put them in `queries` (search terms) or
   `channels` (channel URLs ending in `/videos`). Keep 5-15 queries; each costs a few seconds.
3. Run:

```
uv run --project "${CLAUDE_PLUGIN_ROOT}" clipper discover -n 10
```

4. Show the results as a table: views per day, total views, age, channel, title. It also
   writes `clipper-output/queue.txt`.
5. Point out which ones suit clipping: long, talk-heavy, with reactions (streams, podcasts,
   interviews, debates). Heavily edited videos like MrBeast-style productions have less left to
   cut and are clipped by everyone else too.
6. Offer to clip the ones they choose with `/clipper:clip`.

If they plan to repost other creators' videos, mention once: claims and takedowns are a real
risk, and YouTube gives less reach to channels that mostly re-upload others' clips. Clipping
programs where creators pay for clips, or creators who invite clippers, are the safe options.
