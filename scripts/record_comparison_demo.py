"""Record a GIF of the head-to-head comparison demo.

Starts the Dash app as a background subprocess, drives it with Playwright
while recording video, then converts the captured webm to a GIF via
ffmpeg. Output is written to
examples/pattern_matching_vs_event_bridge/comparison-demo.gif.

Run:
    pip install -e .[integration]
    playwright install chromium
    python scripts/record_comparison_demo.py

Dependencies:
    - playwright (pip install playwright; playwright install chromium)
    - ffmpeg     (brew install ffmpeg)
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_PATH = REPO_ROOT / "examples" / "pattern_matching_vs_event_bridge" / "nested_side_by_side.py"
OUTPUT_GIF = REPO_ROOT / "examples" / "pattern_matching_vs_event_bridge" / "comparison-demo.gif"
APP_URL = "http://127.0.0.1:8050/"

VIEWPORT = {"width": 1600, "height": 960}
GIF_FPS = 10
GIF_WIDTH = 1200
GIF_PALETTE_COLORS = 192
# bayer dither compresses far better than error-diffusion because the
# noise pattern is deterministic (LZW-friendly). bayer_scale=3 gives
# smoother gradients than scale=5 without sierra2_4a's file-size tax.
GIF_DITHER = "bayer:bayer_scale=3"


@contextmanager
def run_app():
    """Launch the demo in a subprocess; terminate on exit."""
    proc = subprocess.Popen(
        [sys.executable, str(APP_PATH)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(REPO_ROOT),
    )
    try:
        for _ in range(40):  # wait up to ~8s for server to be up
            try:
                import urllib.request
                urllib.request.urlopen(APP_URL, timeout=0.5)
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("demo server did not start within 8s")
        yield
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def record_webm(out_dir: pathlib.Path) -> pathlib.Path:
    """Drive the demo in headful Chromium with video recording. Returns webm path."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(out_dir),
            record_video_size=VIEWPORT,
        )
        page = context.new_page()
        page.goto(APP_URL)
        page.wait_for_selector("#cmp-runbtn", state="visible")
        time.sleep(0.8)  # let UI settle before recording meaningful frames
        page.evaluate("document.getElementById('cmp-runbtn').click()")
        # Scripted sequence is 9 clicks * 900ms = 8.1s. The compare panel
        # finalizes ~600ms after the final fetch. 9.5s gives a clean cut
        # without dead idle frames that inflate the GIF.
        time.sleep(9.5)
        page.close()
        context.close()  # flushes video
        browser.close()

    webms = sorted(out_dir.glob("*.webm"))
    if not webms:
        raise RuntimeError(f"no webm written to {out_dir}")
    return webms[-1]


def webm_to_gif(webm: pathlib.Path, gif: pathlib.Path) -> None:
    """Convert webm → gif with palette optimization for smaller files."""
    # Two-pass via lavfi split: palettegen then paletteuse.
    vf = (
        f"fps={GIF_FPS},scale={GIF_WIDTH}:-1:flags=lanczos,"
        f"split[s0][s1];[s0]palettegen=max_colors={GIF_PALETTE_COLORS}[p];"
        f"[s1][p]paletteuse=dither={GIF_DITHER}"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", str(webm),
        "-vf", vf,
        "-loop", "0",
        str(gif),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        with run_app():
            print(f"recording demo at {APP_URL} ...")
            webm = record_webm(tmp_path)
        print(f"captured {webm.name} ({webm.stat().st_size / 1024 / 1024:.1f} MB)")
        print(f"converting to gif: {OUTPUT_GIF}")
        webm_to_gif(webm, OUTPUT_GIF)
    size_mb = OUTPUT_GIF.stat().st_size / 1024 / 1024
    print(f"wrote {OUTPUT_GIF.relative_to(REPO_ROOT)} ({size_mb:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
