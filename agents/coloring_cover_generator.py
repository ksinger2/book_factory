"""
Coloring Book Cover Generator

Generates colored cover and back cover images for coloring books,
with age-appropriate styling and compelling commercial design.
"""

import os
import base64
import logging
import time
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass

try:
    from openai import OpenAI, RateLimitError
except ImportError:
    raise ImportError("openai package required. Install with: pip install openai")


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Age-based cover design rules
COVER_STYLES = {
    "kid": {
        "background": "bright white or soft pastel (light pink, light blue, light yellow)",
        "colors": "bright primary colors (red, blue, yellow) and fun secondary colors",
        "title_style": "big, bubbly, playful font - rainbow or bright colored",
        "sample_style": "1-2 fully colored characters, cute and friendly",
        "mood": "fun, playful, exciting, child-friendly"
    },
    "tween": {
        "background": "white or soft colored background",
        "colors": "vibrant, energetic color palette",
        "title_style": "fun but readable font, colorful",
        "sample_style": "2-3 colored elements showing variety",
        "mood": "energetic, cool, trendy for pre-teens"
    },
    "teen": {
        "background": "can be colored - deep colors acceptable",
        "colors": "trendy, bold color palette (teal, coral, purple)",
        "title_style": "modern font, may be partially colored",
        "sample_style": "mix of colored and line art sections",
        "mood": "artistic, trendy, Instagram-worthy"
    },
    "ya": {
        "background": "dark or sophisticated colored background",
        "colors": "aesthetic palette - muted or jewel tones",
        "title_style": "elegant or artistic font, gold/silver accents",
        "sample_style": "single stunning colored piece or artistic mix",
        "mood": "sophisticated, artistic, mature"
    },
    "adult": {
        "background": "dark (navy, black, deep purple) strongly preferred",
        "colors": "rich jewel tones (emerald, ruby, sapphire, amethyst)",
        "title_style": "elegant serif or script, gold or silver, may have glow",
        "sample_style": "single exquisite colored piece on dark background",
        "mood": "sophisticated, calming, premium quality"
    },
    "elder": {
        "background": "soft, calming colors (sage, cream, soft blue)",
        "colors": "muted, peaceful tones - watercolor feeling",
        "title_style": "classic, readable serif font",
        "sample_style": "fully colored welcoming image",
        "mood": "peaceful, nostalgic, relaxing, accessible"
    }
}


# Art style descriptions - should match the coloring pages
ART_STYLES = {
    "zentangle": "Zentangle - intricate repeating patterns, meditative designs",
    "mandala": "Mandala - circular symmetrical designs, radiating patterns",
    "bold-easy": "Bold & Easy - thick simple outlines, large coloring areas",
    "realistic": "Realistic - fine detailed illustrations, accurate proportions",
    "whimsical": "Whimsical - playful, fun, exaggerated features",
    "botanical": "Botanical - organic flowing lines, naturalistic details",
    "geometric": "Geometric - clean angular shapes, mathematical precision",
    "kawaii": "Kawaii - adorable Japanese-inspired, cute and sweet",
    "stained-glass": "Stained Glass - bold outlines creating mosaic sections",
    "doodle": "Doodle Art - freeform spontaneous, hand-drawn feel"
}


@dataclass
class CoverBrief:
    """Configuration for generating a coloring book cover."""
    title: str
    theme: str
    age_level: str
    difficulty: str
    subtitle: str = ""
    author: str = ""
    notes: str = ""
    style: str = "bold-easy"  # Art style from brief (zentangle, mandala, etc.)


class ColoringCoverGenerator:
    """
    Generate compelling colored covers for coloring books.

    Creates cover and back cover images with age-appropriate styling,
    colored sample artwork, and prominent readable titles.
    """

    def __init__(self, api_key: Optional[str] = None, draft_mode: bool = False):
        """
        Initialize the cover generator.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
            draft_mode: If True, use cheaper models for testing.
        """
        if api_key is None:
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                raise ValueError(
                    "No API key provided. Set OPENAI_API_KEY environment variable."
                )

        self.client = OpenAI(api_key=api_key)
        self.draft_mode = draft_mode

        # Model selection for cost optimization
        if draft_mode:
            self.image_model = "dall-e-2"
            logger.info("Draft mode enabled - using dall-e-2 for cheaper testing")
        else:
            self.image_model = "gpt-image-1"

        self.max_retries = 3
        self.initial_backoff = 30

        logger.info(f"ColoringCoverGenerator initialized with model: {self.image_model}")

    def _save_image(self, image_data: str, output_path: Path) -> None:
        """Save base64-encoded image data to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image_bytes = base64.b64decode(image_data)
        with open(output_path, 'wb') as f:
            f.write(image_bytes)
        logger.info(f"Image saved to {output_path}")

    def _get_cover_style(self, age_level: str) -> Dict[str, str]:
        """Get cover style specifications for an age level."""
        return COVER_STYLES.get(age_level.lower(), COVER_STYLES["adult"])

    def generate_cover(
        self,
        brief: CoverBrief,
        sample_pages: Optional[List[Path]] = None,
        output_path: Optional[Path] = None
    ) -> Tuple[bool, Path]:
        """
        Generate the front cover for a coloring book.

        Creates a compelling commercial cover with:
        - Age-appropriate background color
        - Prominent readable title
        - Colored sample artwork from the book

        Args:
            brief: CoverBrief with title, theme, age level, etc.
            sample_pages: Optional list of sample page paths to use
            output_path: Where to save the cover image

        Returns:
            Tuple of (success, output_path)
        """
        if output_path is None:
            output_path = Path("cover.png")

        cover_style = self._get_cover_style(brief.age_level)

        # Get art style description
        art_style_desc = ART_STYLES.get(brief.style, ART_STYLES["bold-easy"])

        # Build the prompt
        prompt = f"""Generate a COLORING BOOK FRONT COVER for Amazon KDP publishing.

BOOK DETAILS:
- Title: "{brief.title}"
- Theme: {brief.theme}
- Age Level: {brief.age_level}
- Difficulty: {brief.difficulty}
- Art Style: {art_style_desc}
{f"- Subtitle: {brief.subtitle}" if brief.subtitle else ""}
{f"- Author: {brief.author}" if brief.author else ""}

COVER DESIGN SPECIFICATIONS:

BACKGROUND:
{cover_style['background']}

COLOR PALETTE:
{cover_style['colors']}

TITLE TREATMENT:
- Title "{brief.title}" MUST be prominently displayed
- {cover_style['title_style']}
- MUST be readable at thumbnail size (100px wide)
- Position in top third OR bottom third of cover
- High contrast with background for maximum visibility

COLORED SAMPLE ARTWORK:
- {cover_style['sample_style']}
- Show a beautifully colored example from the {brief.theme} theme
- Art style must match: {art_style_desc}
- Colors should be {cover_style['colors']}
- Demonstrates the {brief.difficulty} difficulty level
- Makes viewers want to color the inside pages

MOOD AND FEEL:
{cover_style['mood']}

{f"ADDITIONAL NOTES: {brief.notes}" if brief.notes else ""}

COMMERCIAL QUALITY REQUIREMENTS:
1. Professional Amazon KDP cover quality
2. Title MUST be clearly readable at 160px thumbnail width
3. Compelling and eye-catching design
4. Clean, polished commercial look
5. No copyright-infringing elements
6. Print-ready at 300 DPI
7. Dimensions: 2560 x 1600 pixels (will be cropped to book size)

This cover must drive sales on Amazon - make it compelling and professional."""

        logger.info(f"Generating cover for: {brief.title}")

        # If sample pages provided, use one as reference
        if sample_pages and len(sample_pages) > 0 and sample_pages[0].exists():
            return self._generate_with_reference(prompt, sample_pages[0], output_path)
        else:
            return self._generate_standalone(prompt, output_path)

    def _generate_with_reference(
        self,
        prompt: str,
        reference_path: Path,
        output_path: Path
    ) -> Tuple[bool, Path]:
        """Generate cover using a sample page as reference."""
        for attempt in range(self.max_retries):
            try:
                with open(reference_path, 'rb') as ref_file:
                    ref_prompt = f"""Use the attached coloring page as the basis for the colored sample artwork on this cover.
Color it beautifully with appropriate colors, then incorporate it into the cover design.

{prompt}"""

                    response = self.client.images.edit(
                        model=self.image_model,
                        image=[ref_file],
                        prompt=ref_prompt,
                        size="1024x1536"  # Portrait for cover
                    )

                if response.data[0].b64_json:
                    self._save_image(response.data[0].b64_json, output_path)
                    logger.info("Cover generated successfully with reference")
                    return True, output_path
                else:
                    logger.error("No image data in response")
                    return False, output_path

            except RateLimitError:
                if attempt < self.max_retries - 1:
                    wait_time = self.initial_backoff * (2 ** attempt)
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error("Rate limit exceeded")
                    return False, output_path

            except Exception as e:
                logger.error(f"Error generating cover: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(5)
                else:
                    return False, output_path

        return False, output_path

    def _generate_standalone(
        self,
        prompt: str,
        output_path: Path
    ) -> Tuple[bool, Path]:
        """Generate cover without a reference image."""
        for attempt in range(self.max_retries):
            try:
                response = self.client.images.generate(
                    model=self.image_model,
                    prompt=prompt,
                    size="1024x1536",  # Portrait for cover
                    n=1,
                    quality="medium"
                )

                if response.data[0].b64_json:
                    self._save_image(response.data[0].b64_json, output_path)
                    logger.info("Cover generated successfully")
                    return True, output_path
                else:
                    logger.error("No image data in response")
                    return False, output_path

            except RateLimitError:
                if attempt < self.max_retries - 1:
                    wait_time = self.initial_backoff * (2 ** attempt)
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error("Rate limit exceeded")
                    return False, output_path

            except Exception as e:
                logger.error(f"Error generating cover: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(5)
                else:
                    return False, output_path

        return False, output_path

    def generate_back_cover(
        self,
        brief: CoverBrief,
        sample_pages: Optional[List[Path]] = None,
        output_path: Optional[Path] = None
    ) -> Tuple[bool, Path]:
        """
        Generate the back cover for a coloring book.

        Creates a back cover with:
        - Space for blurb text overlay
        - Preview images of interior pages
        - Barcode area reserved

        Args:
            brief: CoverBrief with title, theme, etc.
            sample_pages: Optional list of sample page paths
            output_path: Where to save the back cover image

        Returns:
            Tuple of (success, output_path)
        """
        if output_path is None:
            output_path = Path("back_cover.png")

        cover_style = self._get_cover_style(brief.age_level)
        art_style_desc = ART_STYLES.get(brief.style, ART_STYLES["bold-easy"])

        prompt = f"""Generate a COLORING BOOK BACK COVER for Amazon KDP publishing.

BOOK DETAILS:
- Title: "{brief.title}"
- Theme: {brief.theme}
- Age Level: {brief.age_level}
- Art Style: {art_style_desc}

BACK COVER DESIGN:

BACKGROUND:
Complementary to front cover - {cover_style['background']}
Should coordinate with the front cover design

LAYOUT REQUIREMENTS:
1. TOP 40%: Leave clean space for text overlay (blurb will be added separately)
   - This area should be relatively simple with subtle background pattern
   - No complex imagery that would interfere with text

2. MIDDLE 35%: Preview images section
   - Show 2-3 small preview thumbnails of colored pages
   - Mix of colored and line art acceptable
   - Demonstrate the variety of content inside

3. BOTTOM 25%: Design element area
   - Include decorative elements matching the theme
   - Leave clear 2" x 1.5" space in bottom right for barcode
   - This barcode area should be a simple light background

STYLE:
- Professional, commercial quality
- Coordinated with front cover design
- {cover_style['mood']}

DO NOT INCLUDE:
- Actual text (blurb will be overlaid separately)
- Barcode graphics
- Price information
- ISBN numbers

Print-ready at 300 DPI, dimensions matching front cover."""

        logger.info(f"Generating back cover for: {brief.title}")

        return self._generate_standalone(prompt, output_path)

    def generate_both(
        self,
        brief: CoverBrief,
        sample_pages: Optional[List[Path]] = None,
        output_dir: Optional[Path] = None
    ) -> Dict[str, Tuple[bool, Path]]:
        """
        Generate both front and back covers.

        Args:
            brief: CoverBrief with book details
            sample_pages: Optional sample pages for reference
            output_dir: Directory to save covers

        Returns:
            Dict with 'cover' and 'back_cover' keys, each with (success, path) tuple
        """
        if output_dir is None:
            output_dir = Path(".")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {}

        # Generate front cover
        cover_path = output_dir / "cover.png"
        results['cover'] = self.generate_cover(brief, sample_pages, cover_path)

        # Generate back cover
        back_path = output_dir / "back_cover.png"
        results['back_cover'] = self.generate_back_cover(brief, sample_pages, back_path)

        return results


def main():
    """Test the cover generator."""
    generator = ColoringCoverGenerator()

    brief = CoverBrief(
        title="Magical Mandalas",
        theme="Mandalas & Patterns",
        age_level="adult",
        difficulty="medium",
        subtitle="A Relaxing Coloring Journey",
        author="Creative Studio"
    )

    output_dir = Path("test_covers")
    results = generator.generate_both(brief, output_dir=output_dir)

    for name, (success, path) in results.items():
        print(f"{name}: {'Success' if success else 'Failed'} - {path}")


if __name__ == "__main__":
    main()
