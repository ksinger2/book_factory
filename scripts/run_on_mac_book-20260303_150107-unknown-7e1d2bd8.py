#!/usr/bin/env python3
"""
Art Generation Script for book-20260303_150107-unknown-7e1d2bd8
Run this on your Mac to generate illustrations using OpenAI DALL-E

Usage:
    python3 scripts/run_on_mac_book-20260303_150107-unknown-7e1d2bd8.py
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Check for OpenAI API key
if not os.environ.get('OPENAI_API_KEY'):
    print("Error: OPENAI_API_KEY not set")
    print("Set it with: export OPENAI_API_KEY='your-key-here'")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai package required")
    print("Install with: pip install openai")
    sys.exit(1)

# Setup
output_dir = Path("output/book-20260303_150107-unknown-7e1d2bd8")
story_path = output_dir / "story_package.json"
art_dir = output_dir / "art"

if not story_path.exists():
    print(f"Error: Story file not found: {story_path}")
    sys.exit(1)

# Load story
with open(story_path, 'r') as f:
    story = json.load(f)

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

# Create art directory
art_dir.mkdir(exist_ok=True)

print(f"Generating illustrations for {story['title']}...")
print(f"Output directory: {art_dir}")

# Generate images for each page
generated_images = {}
for page_num in range(1, story.get('pages', 24) + 1):
    page_key = f"page_{page_num}"

    if page_key not in story.get('art_prompts', {}):
        print(f"Skipping {page_key}: no prompt defined")
        continue

    prompt = story['art_prompts'][page_key]
    art_style = "Soft gouache/watercolor painting. Warm, textured, hand-painted look."
    full_prompt = f"{prompt}\n\nStyle: {art_style}"

    print(f"\nGenerating {page_key}...")
    print(f"Prompt: {prompt[:60]}...")

    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=full_prompt,
            size="1024x1024",
            quality="hd",
            n=1
        )

        image_url = response.data[0].url
        image_path = art_dir / f"{page_key}.json"

        image_data = {
            "page": page_num,
            "prompt": prompt,
            "url": image_url,
            "model": "dall-e-3",
            "generated_at": datetime.now().isoformat()
        }

        with open(image_path, 'w') as f:
            json.dump(image_data, f, indent=2)

        generated_images[page_key] = {
            "url": image_url,
            "path": str(image_path)
        }

        print(f"✓ Generated {page_key}")

    except Exception as e:
        print(f"✗ Failed to generate {page_key}: {e}")

# Save summary
summary = {
    "book_id": "book-20260303_150107-unknown-7e1d2bd8",
    "title": story.get('title'),
    "total_pages": story.get('pages'),
    "generated_count": len(generated_images),
    "generated_at": datetime.now().isoformat(),
    "images": generated_images
}

summary_path = art_dir / "generation_summary.json"
with open(summary_path, 'w') as f:
    json.dump(summary, f, indent=2)

print(f"\n✓ Art generation complete!")
print(f"Generated {len(generated_images)} images")
print(f"Summary saved to: {summary_path}")
print(f"\nNext steps:")
print(f"1. Review images in {art_dir}")
print(f"2. Upload the entire 'art' folder back to the sandbox")
print(f"3. Run: python3 studio.py --pdf-only book-20260303_150107-unknown-7e1d2bd8")
