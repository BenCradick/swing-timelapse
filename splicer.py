#!/usr/bin/env python3
"""
Swing Timelapse Splicer
=======================
Assembles a chronological golf-swing timelapse from dated clip folders.

Folder layout:
    clips/
        2026-10-12/
            swing1.mp4
            swing2.mp4
        2026-11-03/
            best_of_session.mp4

Each dated folder = one practice session. All clips inside are included,
ordered alphabetically. Sessions are ordered by date.

Usage:
    python3 splicer.py                        # build timelapse from clips/
    python3 splicer.py --compare              # add side-by-side (first vs latest) at the end
    python3 splicer.py --max-per-session 2    # cap clips per session (keeps first N)
    python3 splicer.py --seconds-per-clip 2.5 # trim each clip to N seconds

Output: output/timelapse_YYYY-MM-DD.mp4 with date stamps per segment.

Requires: ffmpeg on PATH. Everything else is stdlib.
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CLIPS_DIR = Path(__file__).parent / "clips"
OUTPUT_DIR = Path(__file__).parent / "output"


def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        sys.exit("ERROR: ffmpeg not found on PATH. Install it: https://ffmpeg.org/download.html")


def collect_sessions(max_per_session=None):
    """Return ordered list of (date_str, [video_paths])."""
    if not CLIPS_DIR.exists():
        sys.exit(f"ERROR: {CLIPS_DIR} does not exist.")
    sessions = []
    for d in sorted(CLIPS_DIR.iterdir()):
        if not d.is_dir():
            continue
        try:
            datetime.strptime(d.name, "%Y-%m-%d")
        except ValueError:
            print(f"  ! skipping non-date folder: {d.name}")
            continue
        clips = sorted(
            p for p in d.iterdir()
            if p.suffix.lower() in (".mp4", ".mov", ".m4v", ".avi")
        )
        if not clips:
            print(f"  ! empty session folder: {d.name}")
            continue
        if max_per_session:
            clips = clips[:max_per_session]
        sessions.append((d.name, clips))
    if not sessions:
        sys.exit("ERROR: no dated clip folders found. See README for layout.")
    return sessions


def normalize_clip(src: Path, out: Path, seconds: float, fps: int):
    """Normalize to a common format: same fps, scale, SAR, faststart.
    All clips become 1920x1080 (letterboxed if needed), H.264, no audio.
    Trim to `seconds` from start of clip."""
    vf = (
        f"scale=1920:1080:force_original_aspect_ratio=decrease,"
        f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps={fps}"
    )
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-t", str(seconds),
        "-vf", vf,
        "-an",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        str(out),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def concat_clips(normalized: list, out: Path):
    """Concat normalized clips (same codec params) losslessly."""
    listfile = out.with_suffix(".txt")
    with open(listfile, "w") as f:
        for p in normalized:
            f.write(f"file '{p.resolve()}'\n")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
        "-c", "copy", str(out),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    listfile.unlink()


def date_stamp_overlay(src: Path, out: Path, label: str, fps: int):
    """Re-encode a segment with a date label burned into the top-left corner."""
    text = label.replace(":", r"\:").replace("'", "")
    vf = (
        f"drawtext=text='{label}':"
        f"fontcolor=white:fontsize=48:box=1:boxcolor=black@0.6:"
        f"boxborderw=16:x=40:y=40"
    )
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-vf", vf,
        "-an",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-r", str(fps),
        str(out),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def make_compare(first: Path, last: Path, out: Path, seconds: float, fps: int):
    """Side-by-side: first session (left) vs latest (right), synced by trim length."""
    vf = (
        f"[0:v]trim=0:{seconds},setpts=PTS-STARTPTS,scale=960:1080:force_original_aspect_ratio=decrease,"
        f"pad=960:1080:(ow-iw)/2:(oh-ih)/2,setsar=1[l];"
        f"[1:v]trim=0:{seconds},setpts=PTS-STARTPTS,scale=960:1080:force_original_aspect_ratio=decrease,"
        f"pad=960:1080:(ow-iw)/2:(oh-ih)/2,setsar=1[r];"
        f"[l][r]hstack=inputs=2,fps={fps}"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", str(first), "-i", str(last),
        "-filter_complex", vf,
        "-an",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        str(out),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def main():
    ap = argparse.ArgumentParser(description="Build a golf swing timelapse from dated clip folders.")
    ap.add_argument("--seconds-per-clip", type=float, default=3.0, help="trim each clip to N seconds (default 3)")
    ap.add_argument("--max-per-session", type=int, default=None, help="keep first N clips per session")
    ap.add_argument("--fps", type=int, default=30, help="output fps (default 30)")
    ap.add_argument("--compare", action="store_true", help="append side-by-side first-vs-latest segment")
    args = ap.parse_args()

    check_ffmpeg()
    sessions = collect_sessions(args.max_per_session)

    print(f"Found {len(sessions)} sessions:")
    for date, clips in sessions:
        print(f"  {date}: {len(clips)} clip(s)")

    workdir = OUTPUT_DIR / "work"
    workdir.mkdir(parents=True, exist_ok=True)

    # Normalize every clip, then apply date stamps per session block
    print("Normalizing clips...")
    stamped_segments = []
    for date, clips in sessions:
        for i, clip in enumerate(clips):
            norm = workdir / f"norm_{date}_{i}.mp4"
            normalize_clip(clip, norm, args.seconds_per_clip, args.fps)
            if len(clips) > 1:
                stamped = workdir / f"stamped_{date}_{i}.mp4"
                date_stamp_overlay(norm, stamped, date, args.fps)
                stamped_segments.append(stamped)
            else:
                stamped_segments.append(norm)
        print(f"  {date} done")

    # Optional compare segment: first session's first clip vs latest session's first clip
    if args.compare and len(sessions) >= 2:
        print("Building side-by-side (first vs latest)...")
        first_norm = workdir / "cmp_first.mp4"
        last_norm = workdir / "cmp_last.mp4"
        normalize_clip(sessions[0][1][0], first_norm, args.seconds_per_clip, args.fps)
        normalize_clip(sessions[-1][1][0], last_norm, args.seconds_per_clip, args.fps)
        compare = workdir / "stamped_compare.mp4"
        make_compare(first_norm, last_norm, compare, args.seconds_per_clip, args.fps)
        date_stamp_overlay(compare, workdir / "stamped_compare_lbl.mp4",
                           f"{sessions[0][0]}  vs  {sessions[-1][0]}", args.fps)
        stamped_segments.append(workdir / "stamped_compare_lbl.mp4")
        print("  compare segment done")

    # Concatenate everything
    out_path = OUTPUT_DIR / f"timelapse_{datetime.now().strftime('%Y-%m-%d')}.mp4"
    print(f"Assembling {out_path.name} ({len(stamped_segments)} segments)...")
    concat_clips(stamped_segments, out_path)

    # cleanup work dir
    for p in workdir.iterdir():
        p.unlink()
    workdir.rmdir()

    print(f"\nDone: {out_path}")
    print("Post it. Then drop next month's clips in clips/ and run it again.")


if __name__ == "__main__":
    main()
