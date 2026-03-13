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
        "section_count": "5-10 total sections on the entire page",
        "min_area_size": "Each coloring area at least 1.5 inches across",
        "line_spacing": "Lines must be at least 0.5 inch apart",
        "content": "Simple animals, basic objects, cartoon characters",
        "avoid": "NO intricate patterns, NO textures, NO overlapping elements, NO small details"
    },
    "tween": {
        "line_weight": "2-4pt medium lines",
        "section_count": "15-25 total sections on the entire page",
        "min_area_size": "Each coloring area at least 0.75 inch across",
        "line_spacing": "Lines must be at least 0.25 inch apart",
        "content": "Characters, simple scenes, beginner patterns",
        "avoid": "NO dense patterns, NO very small sections, NO overlapping complex shapes"
    },
    "teen": {
        "line_weight": "1-2pt finer lines",
        "section_count": "30-50 total sections on the entire page",
        "min_area_size": "Each coloring area at least 0.5 inch across",
        "line_spacing": "Lines must be at least 0.15 inch apart",
        "content": "Fantasy, anime-style, detailed characters",
        "avoid": "NO micro-detail patterns, NO sections smaller than a pencil eraser"
    },
    "ya": {
        "line_weight": "0.5-1.5pt fine detailed lines",
        "section_count": "50-80 total sections on the entire page",
        "min_area_size": "Most areas at least 0.25 inch across",
        "line_spacing": "Lines must be at least 0.1 inch apart",
        "content": "Artistic, trendy themes, sophisticated designs",
        "avoid": "NO eye-straining micro-details"
    },
    "adult": {
        "line_weight": "0.25-1pt very fine intricate lines",
        "section_count": "80-150+ total sections on the entire page",
        "min_area_size": "Areas can be as small as 0.1 inch",
        "line_spacing": "Lines can be 0.05 inch apart or closer",
        "content": "Mandalas, botanicals, architecture, complex patterns",
        "avoid": "Generally no restrictions - intricate detail is expected"
    },
    "elder": {
        "line_weight": "1.5-3pt medium-bold clear lines",
        "section_count": "15-30 total sections on the entire page",
        "min_area_size": "Each coloring area at least 0.75 inch across",
        "line_spacing": "Lines must be at least 0.3 inch apart",
        "content": "Nostalgic themes, nature, relaxing scenes",
        "avoid": "NO fine details, NO dense patterns, NO small sections, NO eye strain"
    }
}

# Difficulty modifiers - EXPLICIT rules for what makes coloring easier/harder
DIFFICULTY_MODS = {
    "easy": {
        "multiplier": 0.5,
        "line_thickness": "INCREASE line thickness by 50%",
        "section_reduction": "REDUCE total sections by 50% from age level baseline",
        "min_spacing": "DOUBLE the minimum line spacing",
        "area_increase": "INCREASE minimum coloring area size by 50%",
        "explicit_rules": [
            "MAXIMUM 10-15 distinct coloring sections for the ENTIRE page",
            "Every coloring area must be LARGE - at least 1 inch across",
            "Lines must be THICK and BOLD - easy to see and stay within",
            "NO intricate patterns or textures inside shapes",
            "NO overlapping or layered elements",
            "Simple, clean outlines only",
            "Leave GENEROUS white space between elements",
            "A young child should be able to color this without frustration"
        ]
    },
    "medium": {
        "multiplier": 1.0,
        "line_thickness": "Standard for age level",
        "section_reduction": "Standard section count for age level",
        "min_spacing": "Standard spacing for age level",
        "area_increase": "Standard area sizes for age level",
        "explicit_rules": [
            "Balanced complexity appropriate for age level",
            "Mix of larger and medium-sized coloring areas",
            "Some decorative detail but not overwhelming",
            "Clear distinction between different elements",
            "Comfortable coloring experience - not too easy, not frustrating"
        ]
    },
    "hard": {
        "multiplier": 1.5,
        "line_thickness": "DECREASE line thickness by 25%",
        "section_reduction": "INCREASE sections by 50% from age level baseline",
        "min_spacing": "REDUCE minimum spacing by 25%",
        "area_increase": "REDUCE minimum area size by 25%",
        "explicit_rules": [
            "More detailed and intricate than standard",
            "Include decorative patterns within shapes",
            "Finer line work with more sections",
            "Some challenging small areas mixed with medium ones",
            "Requires patience and precision"
        ]
    },
    "expert": {
        "multiplier": 2.0,
        "line_thickness": "DECREASE line thickness by 50%",
        "section_reduction": "DOUBLE the sections from age level baseline",
        "min_spacing": "REDUCE minimum spacing by 50%",
        "area_increase": "REDUCE minimum area size by 50%",
        "explicit_rules": [
            "Maximum intricacy and detail",
            "Dense patterns and textures throughout",
            "Many small, precise coloring sections",
            "Fine line work requiring steady hand",
            "Challenging even for experienced colorists",
            "May take several hours to complete"
        ]
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

    def __init__(self, api_key: Optional[str] = None, draft_mode: bool = False):
        """
        Initialize the page generator.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
            draft_mode: If True, use cheaper models and settings for testing.
        """
        if api_key is None:
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                raise ValueError(
                    "No API key provided. Set OPENAI_API_KEY environment variable."
                )

        self.client = OpenAI(api_key=api_key)
        self.draft_mode = draft_mode

        # Model and quality selection for cost optimization:
        # - dall-e-2: ~$0.02/image (cheapest, good for drafts)
        # - gpt-image-1: ~$0.04-0.08/image (better quality for production)
        if draft_mode:
            self.image_model = "dall-e-2"
            self.image_quality = "standard"
            self.estimated_cost_per_image = 0.02
            logger.info("Draft mode enabled - using dall-e-2 for cheaper testing")
        else:
            self.image_model = "gpt-image-1"
            self.image_quality = "high"
            self.estimated_cost_per_image = 0.05

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

    def _build_difficulty_prompt(self, age_level: str, difficulty: str) -> str:
        """Build explicit difficulty instructions for the prompt."""
        age_specs = self._get_age_specs(age_level)
        difficulty_mod = self._get_difficulty_mod(difficulty)

        lines = []
        lines.append(f"=== DIFFICULTY LEVEL: {difficulty.upper()} ===")
        lines.append("")

        # Age level baseline
        lines.append(f"BASE SPECIFICATIONS (for {age_level}):")
        lines.append(f"- Target section count: {age_specs['section_count']}")
        lines.append(f"- Minimum coloring area size: {age_specs['min_area_size']}")
        lines.append(f"- Line spacing requirement: {age_specs['line_spacing']}")
        lines.append(f"- Line weight: {age_specs['line_weight']}")
        lines.append(f"- AVOID: {age_specs['avoid']}")
        lines.append("")

        # Difficulty adjustments
        lines.append(f"DIFFICULTY ADJUSTMENTS ({difficulty}):")
        lines.append(f"- {difficulty_mod['line_thickness']}")
        lines.append(f"- {difficulty_mod['section_reduction']}")
        lines.append(f"- {difficulty_mod['min_spacing']}")
        lines.append(f"- {difficulty_mod['area_increase']}")
        lines.append("")

        # Explicit rules
        lines.append("EXPLICIT RULES - MUST FOLLOW:")
        for rule in difficulty_mod['explicit_rules']:
            lines.append(f"• {rule}")

        return "\n".join(lines)

    def generate_page(
        self,
        config: PageConfig,
        reference_sheet: Path,
        output_path: Optional[Path] = None,
        additional_references: Optional[List[Path]] = None
    ) -> Tuple[bool, Path]:
        """
        Generate a single coloring page using the reference sheet as style guide.

        Args:
            config: PageConfig with page details
            reference_sheet: Path to the reference/style sheet image
            output_path: Where to save the generated page
            additional_references: Optional list of additional reference image paths

        Returns:
            Tuple of (success, output_path)
        """
        if not reference_sheet.exists():
            raise FileNotFoundError(f"Reference sheet not found: {reference_sheet}")

        if additional_references is None:
            additional_references = []

        if output_path is None:
            output_path = Path(f"page_{config.page_num:02d}.png")

        # Get age specifications
        age_specs = self._get_age_specs(config.age_level)
        difficulty_mod = self._get_difficulty_mod(config.difficulty)
        theme_guidelines = self._get_theme_guidelines(config.theme)
        difficulty_prompt = self._build_difficulty_prompt(config.age_level, config.difficulty)
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

{difficulty_prompt}

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
□ SECTION COUNT matches difficulty level requirements
□ COLORING AREAS are appropriately sized for difficulty

OUTPUT: Single coloring page with "{config.concept}" fully contained, clear margins on ALL sides, complexity matching {config.difficulty} difficulty."""

        # Log additional references if any
        if additional_references:
            logger.info(f"Generating page {config.page_num} with {len(additional_references)} additional reference(s): {config.concept[:50]}...")
            # Add note about additional references to prompt
            ref_note = f"\n\n*** ADDITIONAL STYLE REFERENCES ***\nUse the additional reference images to match style, line weight, and composition approach."
            prompt = prompt.replace("OUTPUT:", f"{ref_note}\n\nOUTPUT:")
        else:
            logger.info(f"Generating page {config.page_num}: {config.concept[:50]}...")

        # Generate with reference sheet(s)
        for attempt in range(self.max_retries):
            try:
                # Build list of image files - primary reference first, then additional refs
                image_files = []
                ref_file = open(reference_sheet, 'rb')
                image_files.append(ref_file)

                # Add additional reference files
                extra_files = []
                for extra_ref in additional_references:
                    if extra_ref.exists():
                        f = open(extra_ref, 'rb')
                        extra_files.append(f)
                        image_files.append(f)

                try:
                    response = self.client.images.edit(
                        model=self.image_model,
                        image=image_files,
                        prompt=prompt,
                        size="1024x1024"  # Square for coloring pages
                    )
                finally:
                    # Close all files
                    ref_file.close()
                    for f in extra_files:
                        f.close()

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
