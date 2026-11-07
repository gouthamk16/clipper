import pytest

from clipper.bench import grade, spearman
from clipper.cli import posting
from clipper.handoff import clips, transcript
from clipper.perceive import sentences
from clipper.propose import comment_times, peaks, propose, spans
from clipper.rank import rank, total
from clipper.render import ass, chunks, hold, keep


def sents(n, secs=5.0):
    return [{"s": k * secs, "e": (k + 1) * secs, "text": f"line {k}."} for k in range(n)]


def feats(**over):
    base = {"hook": 0.5, "payoff": 0.5, "emotion": 0.5, "surprise": 0.5, "relatable": 0.5,
            "energy": 0.5, "mid_thought": 0.1, "needs_context": 0.1, "sponsor": 0.0, "complete": 0.9}
    return base | over


def test_sentences_split_on_punctuation_and_pauses():
    words = [{"s": 0, "e": 0.4, "w": "Stop."}, {"s": 0.5, "e": 0.9, "w": "wait"},
             {"s": 2.5, "e": 3.0, "w": "now"}]
    assert [s["text"] for s in sentences(words)] == ["Stop.", "wait", "now"]


def test_comment_times_reads_timestamps_and_weights_by_likes():
    comments = [{"text": "9:12 gave me chills", "likes": 500}, {"text": "1:02:03 lol", "likes": 0},
                {"text": "at 0:45 and 0:47", "likes": 0}, {"text": "no stamp", "likes": 9}]
    assert comment_times(comments, dur=900, k=2) == [550, 40]


def test_peaks_are_spaced_apart():
    assert peaks([1, 9, 8, 2, 7], [0, 10, 15, 40, 60], k=2) == [10, 60]


def test_spans_stay_within_length_bounds():
    out = spans(sents(30), [0, 10], min_len=15, max_len=40)
    assert out and all(15 <= (j - i + 1) * 5 <= 40 for i, j in out)


def test_propose_tags_candidates_with_their_reasons():
    meta = {"heatmap": [{"start_time": 50, "end_time": 60, "value": 1.0}], "comments": []}
    cands = propose(sents(30), meta, [0.0] * 300, [0.0] * 30, 15, 40)
    assert any("replayed" in c["why"] and c["s"] <= 50 < c["e"] for c in cands)
    hidden = propose(sents(30), meta, [0.0] * 300, [0.0] * 30, 15, 40, use_heatmap=False)
    assert not any("replayed" in c["why"] for c in hidden)


def test_rank_gates_then_orders_without_overlap():
    cands = [
        {"s": 0, "e": 20, "f": feats(hook=1.0, mid_thought=0.9)},   # best score, but starts mid-thought
        {"s": 30, "e": 50, "f": feats(hook=0.9)},
        {"s": 40, "e": 60, "f": feats(hook=0.8)},                   # overlaps the one above
        {"s": 70, "e": 90, "f": feats(hook=0.2)},
        {"s": 100, "e": 120, "f": feats(hook=1.0, complete=0.1)},   # ends unfinished
    ]
    assert [(c["s"], c["e"]) for c in rank(cands, 5)] == [(30, 50), (70, 90)]


def test_total_ignores_missing_replay():
    assert total(feats()) == total(feats(replay=0.5))


def test_captions_highlight_each_word_in_turn():
    words = [{"s": 10.0, "e": 10.3, "w": "one"}, {"s": 10.3, "e": 10.6, "w": "two."},
             {"s": 11.5, "e": 11.9, "w": "three"}]
    assert [[w["w"] for w in g] for g in chunks(words)] == [["one", "two."], ["three"]]
    segs, timed, dur = keep(words, 9.0, 13.0)
    assert [(round(a, 2), round(b, 2)) for a, b in segs] == [(0.8, 1.8), (2.3, 3.1)]   # the 0.9s pause is cut
    assert round(dur, 2) == 1.8
    assert [round(w["s"], 2) for w in timed] == [0.2, 0.5, 1.2]
    lines = [l for l in ass(timed, dur, "Big claim", "Arial").splitlines() if l.startswith("Dialogue")]
    assert lines[0].endswith("Title,,0,0,0,,Big claim")
    assert lines[1].startswith("Dialogue: 0,0:00:00.20,0:00:00.50,Cap") and "}ONE{" in lines[1]
    assert "}TWO.{" in lines[2] and "}THREE{" in lines[3]


def test_grade_rewards_picks_on_replayed_moments():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    heat = [{"start_time": t, "end_time": t + 10, "value": 1.0 if t == 50 else 0.1} for t in range(0, 100, 10)]
    cands = [{"id": str(t), "s": t, "e": t + 10, "f": feats(hook=1.0 if t == 50 else 0.1)} for t in range(0, 100, 10)]
    g = grade(cands, heat, [0.0] * 200, n=1)
    assert g["lift"] > 5 and g["hit"] == 1.0 and g["chance"] == 0.1 and g["rho"]["hook"] > 0


def test_crop_holds_through_a_glance_and_cuts_on_a_real_switch():
    left, right = 300.0, 1500.0
    picks = [(k * 0.25, x) for k, x in enumerate([left] * 4 + [right] + [left] * 3 + [right] * 4)]
    assert hold(picks, jump=190) == [(0.0, left), (2.0, right)]


def test_transcript_tags_sentences_the_audience_points_at():
    text = transcript(sents(4), {"replayed": [11.0], "loud": []}, {"title": "T", "channel": "C"}, {"funny": 3.0})
    assert "[2] 00:10.0-00:15.0 (replayed) line 2." in text and "[1] 00:05.0-00:10.0 line 1." in text
    assert "#funny" in text


def test_picks_become_clips_and_posting_uses_claudes_words():
    picks = [{"start": 1, "end": 2, "hook": "Wait for it", "title": "He actually did it",
              "description": "The moment it clicked.", "hashtags": ["#gaming", "shorts"]}]
    [c] = clips(picks, sents(4))
    assert (c["s"], c["e"], c["title"], c["tags"]) == (5.0, 15.0, "Wait for it", ["gaming", "shorts"])
    text = posting(c, {"title": "Source", "channel": "Chan", "url": "https://x"})
    assert "He actually did it #shorts" in text and "The moment it clicked." in text
    assert text.count("#shorts") == 2   # once in the title, once in the tags, not duplicated
    with pytest.raises(ValueError):
        clips([{"start": 3, "end": 9}], sents(4))
