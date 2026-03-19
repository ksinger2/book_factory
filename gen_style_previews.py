#!/usr/bin/env python3
"""
Generate preview thumbnail images for each built-in art style.

Produces one 1024x1024 PNG per style in resources/style_previews/ using a
consistent scene prompt so styles can be compared side-by-side.
"""
import os
import sys
import base64
import logging
from pathlib import Path

try:
    from openai import OpenAI, RateLimitError
except ImportError:
    print("Error: openai package not found. Install with: pip install openai")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger("style_previews")

OUTPUT_DIR = Path(__file__).parent / "resources" / "style_previews"

SCENE_PROMPT = "A friendly fox sitting in a sunny forest clearing, children's book illustration"

STYLES = {
    "gouache": (
        "Soft gouache/watercolor painting. Warm, textured, hand-painted look "
        "with visible brush strokes and soft color bleeds."
    ),
    "digital": (
        "Clean digital illustration with soft gradients, vibrant saturated colors, "
        "smooth lines, and a polished modern feel."
    ),
    "colored_pencil": (
        "Colored pencil illustration with visible pencil strokes, gentle shading, "
        "and a handmade, textured quality on paper."
    ),
    "flat": (
        "Modern flat illustration with bold solid colors, simple geometric shapes, "
        "minimal shading, and clean graphic design aesthetic."
    ),
    "ghibli": (
        "In the style of Studio Ghibli: Whimsical hand-painted animated film still "
        "with lush natural details, soft lighting, and a sense of wonder."
    ),
    "tim_burton": (
        "Illustrated in a dark whimsical gothic fantasy style with exaggerated "
        "proportions, spindly shapes, high contrast, and eerie charm."
    ),
}


def generate_preview(client: OpenAI, style_key: str, style_desc: str) -> Path:
    """Generate a single style preview image and save it as PNG."""
    prompt = f"{style_desc}\n\n{SCENE_PROMPT}"
    log.info(f"Generating preview for style '{style_key}'...")

    response = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024",
        quality="low",
        n=1,
    )

    # gpt-image-1 returns base64 data by default
    image_b64 = response.data[0].b64_json
    if image_b64 is None:
        # Fall back to URL download if b64 wasn't returned
        import requests
        img_bytes = requests.get(response.data[0].url).content
    else:
        img_bytes = base64.b64decode(image_b64)

    out_path = OUTPUT_DIR / f"{style_key}.png"
    out_path.write_bytes(img_bytes)
    log.info(f"  Saved {out_path} ({len(img_bytes)} bytes)")
    return out_path


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        sys.exit(1)

    client = OpenAI(api_key=api_key, timeout=180.0)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating {len(STYLES)} style preview thumbnails...")
    print(f"Output directory: {OUTPUT_DIR}\n")

    results = {}
    for style_key, style_desc in STYLES.items():
        try:
            path = generate_preview(client, style_key, style_desc)
            results[style_key] = ("OK", path)
        except Exception as e:
            log.error(f"  FAILED for '{style_key}': {e}")
            results[style_key] = ("FAILED", str(e))

    # Summary
    print("\n--- Results ---")
    for style_key, (status, detail) in results.items():
        print(f"  {style_key:16s} {status:6s}  {detail}")

    failed = sum(1 for s, _ in results.values() if s == "FAILED")
    if failed:
        print(f"\n{failed}/{len(STYLES)} previews failed.")
        sys.exit(1)
    else:
        print(f"\nAll {len(STYLES)} previews generated successfully.")


if __name__ == "__main__":
    main()
