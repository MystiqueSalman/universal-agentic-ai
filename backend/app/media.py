"""Media pipeline (Batch 08; Doc 12 precursor).

What is real here: FFmpeg assembly of a genuine, playable MP4 preview from
scene cards (title + scene list derived from the production plan). What it
is NOT: AI-generated video footage. The render is labelled 'scene-card
preview' on its face and in every artifact that references it; generative
video models plug into this same pipeline via the Model Router later.
"""
from __future__ import annotations

import os
import subprocess

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SEG_SECONDS = 2


def _esc(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
            .replace("%", "\\%"))[:60]


def _segment(path: str, text: str, color: str) -> None:
    vf = (f"drawtext=fontfile={FONT}:text='{_esc(text)}':fontcolor=white:fontsize=38:"
          f"x=(w-text_w)/2:y=(h-text_h)/2")
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    f"color=c={color}:s=1280x720:d={SEG_SECONDS}:r=24",
                    "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", path],
                   check=True, capture_output=True, timeout=120)


def build_preview_mp4(folder: str, title: str, scenes: list[str]) -> str:
    """Render a scene-card preview MP4 into folder; returns the file path."""
    os.makedirs(folder, exist_ok=True)
    cards = [f"UNIVERSAL AGENTIC AI — PREVIEW", title] + [f"Scene {i + 1}: {s}" for i, s in enumerate(scenes[:8])]
    colors = ["0x0a1830", "0x12315e", "0x0e4a6e", "0x134e4a", "0x3b0764", "0x7c2d12"]
    segs = []
    for i, card in enumerate(cards):
        seg = os.path.join(folder, f"_seg{i:02d}.mp4")
        _segment(seg, card, colors[i % len(colors)])
        segs.append(seg)
    listfile = os.path.join(folder, "_concat.txt")
    with open(listfile, "w") as f:
        for seg in segs:
            f.write(f"file '{os.path.basename(seg)}'\n")
    out = os.path.join(folder, "preview.mp4")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                    "-c", "copy", out], check=True, capture_output=True, timeout=180)
    for seg in segs:
        os.remove(seg)
    os.remove(listfile)
    return out


def probe_duration(path: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True, timeout=60)
    return float(r.stdout.strip() or 0)
