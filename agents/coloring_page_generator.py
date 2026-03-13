"""
Coloring Page Generator

Generates individual coloring book pages using a reference style sheet
for visual consistency throughout the book.
"""

import os
import base64
import logging
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass, field

try:
    from openai import OpenAI, RateLimitError
except ImportError:
    raise ImportError("openai package required. Install with: pip install openai")


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Age level specifications
AGE_SPECS = {
    "kid": {
        "line_weight": "4-6pt thick bold lines",
        "planes": "3-8 planes per object",
        "areas": "Extra large coloring areas",
        "content": "Simple animals, basic objects, cartoon characters"
    },
    "tween": {
        "line_weight": "2-4pt medium lines",
        "planes": "10-20 planes per object",
        "areas": "Medium sized coloring areas",
        "content": "Characters, simple scenes, beginner patterns"
    },
    "teen": {
        "line_weight": "1-2pt finer lines",
        "planes": "20-40 planes per object",
        "areas": "Varied size coloring areas",
        "content": "Fantasy, anime-style, detailed characters"
    },
    "ya": {
        "line_weight": "0.5-1.5pt fine detailed lines",
        "planes": "30-50 planes per object",
        "areas": "Mix of large and detailed small areas",
        "content": "Artistic, trendy themes, sophisticated designs"
    },
    "adult": {
        "line_weight": "0.25-1pt very fine intricate lines",
        "planes": "40-80+ planes per object",
        "areas": "Many small detailed sections",
        "content": "Mandalas, botanicals, architecture, complex patterns"
    },
    "elder": {
        "line_weight": "1.5-3pt medium-bold clear lines",
        "planes": "15-30 planes per object",
        "areas": "Larger, well-defined areas",
        "content": "Nostalgic themes, nature, relaxing scenes"
    }
}

# Difficulty modifiers with plane multiplier
DIFFICULTY_MODS = {
    "easy": {
        "plane_mod": 0.5,
        "description": "Reduce complexity by 50%, widen coloring areas, thicken lines"
    },
    "medium": {
        "plane_mod": 1.0,
        "description": "Standard specifications for age level"
    },
    "hard": {
        "plane_mod": 1.5,
        "description": "Increase complexity by 50%, add fine details, thinner lines"
    },
    "expert": {
        "plane_mod": 2.0,
        "description": "Double complexity, maximum intricacy, finest appropriate lines"
    }
}

# Theme guidelines for consistent style
THEME_GUIDELINES = {
    "mandalas": "Circular symmetry, radiating patterns, balance complexity from center outward",
    "animals": "Clear silhouettes, texture through line patterns, expressive but simple features",
    "nature": "Organic flowing lines, leaf veins and petal details, layered natural elements",
    "fantasy": "Dramatic poses, mix geometric and organic, magical effects like stars and swirls",
    "aquatic": "Flowing wave patterns, scale patterns, coral and seaweed textures",
    "architecture": "Precise geometric lines, perspective accuracy, texture patterns",
    "food": "Rounded appetizing shapes, texture details, playful arrangements",
    "holidays": "Season-appropriate elements, festive decorations, themed objects",
    "quotes": "Typography-friendly layouts, decorative borders, frame elements",
    "insects": "Detailed wing patterns, segmented body structure, antennae and leg details",
    "bugs": "Detailed wing patterns, segmented body structure, antennae and leg details",
    "birds": "Feather texture patterns, wing details, expressive poses",
    "custom": "Follow the specific theme description provided"
}


# Art style descriptions for different coloring book styles
ART_STYLES = {
    "zentangle": "Zentangle style - intricate repeating patterns, meditative designs, organic shapes flowing into each other",
    "mandala": "Mandala style - circular symmetrical designs, radiating patterns from center",
    "bold-easy": "Bold & Easy style - thick simple outlines, large coloring areas, minimal detail, beginner-friendly",
    "realistic": "Realistic/Detailed style - fine detailed illustrations, accurate proportions, subtle textures",
    "whimsical": "Whimsical/Cartoon style - playful, fun, exaggerated features, lighthearted and cheerful",
    "botanical": "Botanical/Nature style - organic flowing lines, naturalistic plant details, delicate leaf veins",
    "geometric": "Geometric/Abstract style - clean angular shapes, patterns, mathematical precision",
    "kawaii": "Kawaii/Cute style - adorable Japanese-inspired, round shapes, big eyes, sweet expressions",
    "stained-glass": "Stained Glass style - bold black outlines creating mosaic-like sections, compartmentalized design",
    "doodle": "Doodle Art style - freeform spontaneous drawing, hand-drawn feel, casual and organic"
}


@dataclass
class PageConfig:
    """Configuration for a coloring page."""
    page_num: int
    concept: str
    theme: str
    age_level: str
    difficulty: str
    notes: str = ""
    style: str = "bold-easy"
    previous_subjects: List[str] = field(default_factory=list)


class ColoringPageGenerator:
    """
    Generate individual coloring book pages with style consistency.

    Uses OpenAI's image generation API with a reference style sheet
    to maintain consistent visual language throughout the book.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the page generator.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
        """
        if api_key is None:
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                raise ValueError(
                    "No API key provided. Set OPENAI_API_KEY environment variable."
                )

        self.client = OpenAI(api_key=api_key)
        self.image_model = "gpt-image-1"
        self.max_retries = 3
        self.initial_backoff = 30

        logger.info(f"ColoringPageGenerator initialized with model: {self.image_model}")

    def _image_to_base64(self, image_path: Path) -> str:
        """Convert image file to base64."""
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def _save_image(self, image_data: str, output_path: Path) -> None:
        """Save base64-encoded image data to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image_bytes = base64.b64decode(image_data)
        with open(output_path, 'wb') as f:
            f.write(image_bytes)
        logger.info(f"Image saved to {output_path}")

    def _get_age_specs(self, age_level: str) -> Dict[str, str]:
        """Get specifications for an age level."""
        return AGE_SPECS.get(age_level.lower(), AGE_SPECS["adult"])

    def _get_difficulty_mod(self, difficulty: str) -> Dict[str, Any]:
        """Get difficulty modifier."""
        return DIFFICULTY_MODS.get(difficulty.lower(), DIFFICULTY_MODS["medium"])

    def _get_theme_guidelines(self, theme: str) -> str:
        """Get guidelines for a theme."""
        theme_lower = theme.lower()
        for key, guidelines in THEME_GUIDELINES.items():
            if key in theme_lower:
                return guidelines
        return THEME_GUIDELINES["custom"]

    def _calculate_complexity(self, age_level: str, difficulty: str) -> str:
        """Calculate adjusted complexity based on age and difficulty."""
        age_specs = self._get_age_specs(age_level)
        difficulty_mod = self._get_difficulty_mod(difficulty)
        planes = age_specs['planes']
        # Extract base number for calculation note
        mod = difficulty_mod['plane_mod']
        if mod == 0.5:
            return f"{planes} reduced by 50% (simpler, larger areas)"
        elif mod == 1.5:
            return f"{planes} increased by 50% (more detailed)"
        elif mod == 2.0:
            return f"{planes} doubled (maximum intricacy)"
        return planes

    def generate_page(
        self,
        config: PageConfig,
        reference_sheet: Path,
        output_path: Optional[Path] = None
    ) -> Tuple[bool, Path]:
        """
        Generate a single coloring page using the reference sheet as style guide.

        Args:
            config: PageConfig with page details
            reference_sheet: Path to the reference/style sheet image
            output_path: Where to save the generated page

        Returns:
            Tuple of (success, output_path)
        """
        if not reference_sheet.exists():
            raise FileNotFoundError(f"Reference sheet not found: {reference_sheet}")

        if output_path is None:
            output_path = Path(f"page_{config.page_num:02d}.png")

        # Get age specifications
        age_specs = self._get_age_specs(config.age_level)
        difficulty_mod = self._get_difficulty_mod(config.difficulty)
        theme_guidelines = self._get_theme_guidelines(config.theme)
        calculated_complexity = self._calculate_complexity(config.age_level, config.difficulty)
        art_style = ART_STYLES.get(config.style, ART_STYLES["bold-easy"])

        # Build the prompt with safe zone framing FIRST
        prompt = f"""Generate a coloring book page for: {config.concept}

*** CRITICAL - SAFE ZONE FRAMING - READ FIRST ***
- Draw ENTIRE subject within the INNER 80% of canvas
- 10% invisible margin on ALL edges - NOTHING enters this zone
- Subject must be FULLY VISIBLE: head, tail, wings, limbs - ALL parts complete
- If too large, SHRINK IT to fit completely

FAILURE EXAMPLES TO AVOID:
- Dragon with tail cut off at edge
- Unicorn with horn cropped at top
- Character missing feet at bottom
- Wings extending past side edges
- Butterfly antenna touching top edge
- Fish tail disappearing at bottom

COMPOSITION CHECK (verify ALL before drawing):
✓ Can I see the TOP of the subject? If NO → shrink
✓ Can I see the BOTTOM? If NO → shrink
✓ Can I see LEFT and RIGHT edges completely? If NO → shrink
✓ Is there clear white space between subject and ALL 4 edges? If NO → shrink

*** MAIN SUBJECT ***
Draw: {config.concept}
Size: 50-70% of the SAFE ZONE (not the whole page)
Position: CENTERED with generous margins all around

*** ART STYLE ***
{art_style}

*** UNIQUENESS - DO NOT REPEAT ***
Already used in this book: {', '.join(config.previous_subjects) if config.previous_subjects else 'None yet'}
Your subject "{config.concept}" must look COMPLETELY DIFFERENT from above.
- Page {config.page_num} in a coloring book
- Create a fresh, distinct composition unlike any previous page

LINE STYLE (match reference sheet):
- Line Weight: {age_specs['line_weight']}
- Complexity: {calculated_complexity}
- Content: {age_specs['content']}

{f"NOTES: {config.notes}" if config.notes else ""}

TECHNICAL REQUIREMENTS:
1. PURE BLACK LINES on WHITE background ONLY
2. NO colors, gradients, shading, or gray tones
3. ALL shapes must be CLOSED - no open-ended lines
4. NO text, labels, or writing
5. NO watermarks or signatures
6. ZERO random dots, specks, or stray marks
7. Background must be PERFECTLY clean pure white

*** FINAL CHECK - MANDATORY ***
Before outputting, verify:
□ The ENTIRE {config.concept} is 100% visible
□ NO part of the subject touches ANY edge
□ Clear white margin visible on all 4 sides
□ If ANY part would be cut off, you made it SMALLER

OUTPUT: Single coloring page with "{config.concept}" fully contained, clear margins on ALL sides."""

        logger.info(f"Generating page {config.page_num}: {config.concept[:50]}...")

        # Generate with reference sheet
        for attempt in range(self.max_retries):
            try:
                with open(reference_sheet, 'rb') as ref_file:
                    response = self.client.images.edit(
                        model=self.image_model,
                        image=[ref_file],
                        prompt=prompt,
                        size="1024x1024"  # Square for coloring pages
                    )

                # Save the result
                if response.data[0].b64_json:
                    self._save_image(response.data[0].b64_json, output_path)
                    logger.info(f"Page {config.page_num} generated successfully")
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
                    logger.error("Rate limit exceeded after max retries")
                    return False, output_path

            except Exception as e:
                logger.error(f"Error generating page {config.page_num}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(5)
                else:
                    return False, output_path

        return False, output_path

    def generate_page_without_reference(
        self,
        config: PageConfig,
        output_path: Optional[Path] = None
    ) -> Tuple[bool, Path]:
        """
        Generate a coloring page without a reference sheet.
        Used when reference sheet is not available or for standalone pages.

        Args:
            config: PageConfig with page details
            output_path: Where to save the generated page

        Returns:
            Tuple of (success, output_path)
        """
        if output_path is None:
            output_path = Path(f"page_{config.page_num:02d}.png")

        # Get age specifications
        age_specs = self._get_age_specs(config.age_level)
        difficulty_mod = self._get_difficulty_mod(config.difficulty)

        # Build the prompt
        prompt = f"""Generate a COLORING BOOK PAGE.

PAGE DETAILS:
- Page Number: {config.page_num}
- Concept: {config.concept}
- Theme: {config.theme}

AGE LEVEL SPECIFICATIONS ({config.age_level}):
- Line Weight: {age_specs['line_weight']}
- Complexity: {age_specs['planes']}
- Coloring Areas: {age_specs['areas']}
- Content Style: {age_specs['content']}

DIFFICULTY ADJUSTMENT ({config.difficulty}):
{difficulty_mod}

{f"ADDITIONAL NOTES: {config.notes}" if config.notes else ""}

CRITICAL REQUIREMENTS:
1. PURE BLACK LINES on WHITE background ONLY
2. NO colors, gradients, shading, or gray tones
3. ALL shapes must be CLOSED - no open lines
4. Line weight: {age_specs['line_weight']}
5. Clean intersections where lines meet
6. NO text, labels, or writing
7. Print-ready quality at 300 DPI

Single coloring page, pure black lines on white background."""

        logger.info(f"Generating page {config.page_num} (no reference): {config.concept[:50]}...")

        for attempt in range(self.max_retries):
            try:
                response = self.client.images.generate(
                    model=self.image_model,
                    prompt=prompt,
                    size="1024x1024",
                    n=1,
                    quality="medium"
                )

                if response.data[0].b64_json:
                    self._save_image(response.data[0].b64_json, output_path)
                    logger.info(f"Page {config.page_num} generated successfully")
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
                    logger.error("Rate limit exceeded after max retries")
                    return False, output_path

            except Exception as e:
                logger.error(f"Error generating page {config.page_num}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(5)
                else:
                    return False, output_path

        return False, output_path

    def generate_batch(
        self,
        configs: list,
        reference_sheet: Path,
        output_dir: Path,
        qa_checker=None,
        max_qa_retries: int = 3
    ) -> Dict[int, Dict[str, Any]]:
        """
        Generate multiple pages with optional QA checking.

        Args:
            configs: List of PageConfig objects
            reference_sheet: Path to reference sheet
            output_dir: Directory to save pages
            qa_checker: Optional ColoringQAChecker instance
            max_qa_retries: Max retries per page if QA fails

        Returns:
            Dict mapping page number to result info
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {}

        for config in configs:
            output_path = output_dir / f"page_{config.page_num:02d}.png"
            qa_attempts = 0
            success = False

            while qa_attempts < max_qa_retries and not success:
                # Generate the page
                gen_success, path = self.generate_page(
                    config, reference_sheet, output_path
                )

                if not gen_success:
                    qa_attempts += 1
                    continue

                # Run QA if checker provided
                if qa_checker:
                    qa_result = qa_checker.check_page(
                        path,
                        config.age_level,
                        config.difficulty,
                        config.theme
                    )

                    if qa_result.passed:
                        success = True
                        results[config.page_num] = {
                            "success": True,
                            "path": str(path),
                            "qa_passed": True,
                            "qa_scores": qa_result.scores,
                            "attempts": qa_attempts + 1
                        }
                    else:
                        logger.warning(
                            f"Page {config.page_num} failed QA (attempt {qa_attempts + 1}): "
                            f"{qa_result.summary}"
                        )
                        qa_attempts += 1
                else:
                    # No QA checker, assume success
                    success = True
                    results[config.page_num] = {
                        "success": True,
                        "path": str(path),
                        "qa_passed": None,
                        "attempts": qa_attempts + 1
                    }

            if not success:
                results[config.page_num] = {
                    "success": False,
                    "path": str(output_path) if output_path.exists() else None,
                    "qa_passed": False,
                    "attempts": qa_attempts,
                    "error": f"Failed after {max_qa_retries} attempts"
                }

        return results


def main():
    """Test the page generator."""
    import sys

    # Example usage
    generator = ColoringPageGenerator()

    config = PageConfig(
        page_num=1,
        concept="A friendly dragon sitting on a treasure pile",
        theme="Fantasy",
        age_level="teen",
        difficulty="medium"
    )

    output_path = Path("test_coloring_page.png")
    success, path = generator.generate_page_without_reference(config, output_path)

    print(f"Generation {'succeeded' if success else 'failed'}: {path}")


if __name__ == "__main__":
    main()
