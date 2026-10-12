# swing-timelapse

A swing-improvement timelapse pipeline: film one good swing per practice session, drop it in a dated folder, run one command, get a dated, stitched timelapse video — with an optional first-vs-latest side-by-side for progress posts.

Built for the "documented swing rebuild" content series. Designed to be dead simple: the only manual step is saving one 3-4 second clip per session.

## Workflow

1. **At the range/sim:** film swings at 120fps (slow-mo), fixed camera position — down-the-line, chest height, tripod.
2. **After the session:** trim your best representative swing to ~3-4 seconds and save it as:

```
clips/
    2026-10-12/
        swing.mp4
    2026-11-03/
        swing.mp4
```

Folder name = session date (`YYYY-MM-DD`). One clip per folder is fine; multiple clips work too (they play in alphabetical order).

3. **Build the timelapse:**

```bash
python3 splicer.py
```

Output lands in `output/timelapse_<today>.mp4` with date stamps burned into each session segment.

## Options

```bash
python3 splicer.py --compare               # append side-by-side: first session vs latest
python3 splicer.py --max-per-session 2     # cap clips per session (keeps first N)
python3 splicer.py --seconds-per-clip 2.5  # trim each clip to N seconds (default 3)
python3 splicer.py --fps 60                # output fps (default 30)
```

`--compare` is the money shot for progress posts: oldest swing on the left, newest on the right, synced and labeled.

## Requirements

- Python 3.8+ (stdlib only)
- [ffmpeg](https://ffmpeg.org/download.html) on PATH

## Notes

- All clips are normalized to 1080p H.264 (letterboxed if needed), so mixed phone orientations/formats are fine — but consistent framing makes the result far better.
- Audio is stripped (irrelevant for a timelapse, halves the file size).
- Slow-mo source footage (120fps) is kept at normal speed after trimming — the timelapse shows real-time swings per session. If you want true slow-motion segments, change `-t` handling in `normalize_clip` and drop the `fps` filter.

## Roadmap

- [ ] Progress-tracking CSV (date, club, carry, dispersion) → stats overlay per segment
- [ ] True slow-mo segment option
- [ ] Face-on + down-the-line dual-angle layout
