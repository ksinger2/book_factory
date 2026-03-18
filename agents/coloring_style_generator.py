"""
Coloring Style Generator

Generates reference/style sheets for coloring books that establish
the visual language, line weights, and complexity for all pages.
"""

import os
import base64
import logging
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
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


# Age level specifications with explicit sizing requirements
AGE_SPECS = {
    "kid": {
        "line_weight": "4-6pt thick bold lines",
        "section_count": "5-10 total sections on the entire page",
        "min_area_size": "Each coloring area at least 1.5 inches across",
        "line_spacing": "Lines must be at least 0.5 inch apart",
        "content": "Simple animals, basic objects, cartoon characters",
        "description": "Ages 3-6, very simple shapes with thick outlines",
        "avoid": "NO intricate patterns, NO textures, NO overlapping elements, NO small details"
    },
    "tween": {
        "line_weight": "2-4pt medium lines",
        "section_count": "15-25 total sections on the entire page",
        "min_area_size": "Each coloring area at least 0.75 inch across",
        "line_spacing": "Lines must be at least 0.25 inch apart",
        "content": "Characters, simple scenes, beginner patterns",
        "description": "Ages 7-12, moderate detail with clear shapes",
        "avoid": "NO dense patterns, NO very small sections, NO overlapping complex shapes"
    },
    "teen": {
        "line_weight": "1-2pt finer lines",
        "section_count": "30-50 total sections on the entire page",
        "min_area_size": "Each coloring area at least 0.5 inch across",
        "line_spacing": "Lines must be at least 0.15 inch apart",
        "content": "Fantasy, anime-style, detailed characters",
        "description": "Ages 13-17, detailed with intricate elements",
        "avoid": "NO micro-detail patterns, NO sections smaller than a pencil eraser"
    },
    "ya": {
        "line_weight": "0.5-1.5pt fine detailed lines",
        "section_count": "50-80 total sections on the entire page",
        "min_area_size": "Most areas at least 0.25 inch across",
        "line_spacing": "Lines must be at least 0.1 inch apart",
        "content": "Artistic, trendy themes, sophisticated designs",
        "description": "Ages 18-25, sophisticated artistic style",
        "avoid": "NO eye-straining micro-details"
    },
    "adult": {
        "line_weight": "0.25-1pt very fine intricate lines",
        "section_count": "80-150+ total sections on the entire page",
        "min_area_size": "Areas can be as small as 0.1 inch",
        "line_spacing": "Lines can be 0.05 inch apart or closer",
        "content": "Mandalas, botanicals, architecture, complex patterns",
        "description": "Ages 26-55, highly intricate designs",
        "avoid": "Generally no restrictions - intricate detail is expected"
    },
    "elder": {
        "line_weight": "1.5-3pt medium-bold clear lines",
        "section_count": "15-30 total sections on the entire page",
        "min_area_size": "Each coloring area at least 0.75 inch across",
        "line_spacing": "Lines must be at least 0.3 inch apart",
        "content": "Nostalgic themes, nature, relaxing scenes",
        "description": "Ages 55+, clear shapes with moderate detail",
        "avoid": "NO fine details, NO dense patterns, NO small sections, NO eye strain"
    }
}

# Theme guidelines
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

# Difficulty modifiers - EXPLICIT rules for what makes coloring easier/harder
DIFFICULTY_MODS = {
    "easy": {
        "multiplier": 0.5,
        "description": "Reduce complexity by 50%, wider coloring areas, thicker lines",
        "explicit_rules": [
            "MAXIMUM 10-15 distinct coloring sections for the ENTIRE page",
            "Every coloring area must be LARGE - at least 1 inch across",
            "Lines must be THICK and BOLD - easy to see and stay within",
            "NO intricate patterns or textures inside shapes",
            "NO overlapping or layered elements",
            "Simple, clean outlines only",
            "Leave GENEROUS white space between elements"
        ]
    },
    "medium": {
        "multiplier": 1.0,
        "description": "Standard specifications for age level",
        "explicit_rules": [
            "Balanced complexity appropriate for age level",
            "Mix of larger and medium-sized coloring areas",
            "Some decorative detail but not overwhelming",
            "Clear distinction between different elements"
        ]
    },
    "hard": {
        "multiplier": 1.5,
        "description": "Increase complexity by 50%, add fine details",
        "explicit_rules": [
            "More detailed and intricate than standard",
            "Include decorative patterns within shapes",
            "Finer line work with more sections",
            "Some challenging small areas mixed with medium ones"
        ]
    },
    "expert": {
        "multiplier": 2.0,
        "description": "Double complexity, maximum intricacy",
        "explicit_rules": [
            "Maximum intricacy and detail",
            "Dense patterns and textures throughout",
            "Many small, precise coloring sections",
            "Fine line work requiring steady hand"
        ]
    }
}

# Art style descriptions - defines the visual approach
ART_STYLES = {
    "zentangle": "Zentangle style - intricate repeating patterns, meditative designs, organic shapes flowing into each other",
    "mandala": "Mandala style - circular symmetrical designs, radiating patterns from center, sacred geometry feel",
    "bold-easy": "Bold & Easy style - thick simple outlines, large coloring areas, minimal detail, beginner-friendly approach",
    "realistic": "Realistic/Detailed style - fine detailed illustrations, accurate proportions, subtle textures",
    "whimsical": "Whimsical/Cartoon style - playful, fun, exaggerated features, lighthearted and cheerful",
    "botanical": "Botanical/Nature style - organic flowing lines, naturalistic plant details, delicate leaf veins",
    "geometric": "Geometric/Abstract style - clean angular shapes, patterns, mathematical precision",
    "kawaii": "Kawaii/Cute style - adorable Japanese-inspired, round shapes, big eyes, sweet expressions",
    "stained-glass": "Stained Glass style - bold black outlines creating mosaic-like sections, compartmentalized design",
    "doodle": "Doodle Art style - freeform spontaneous drawing, hand-drawn feel, casual and organic"
}


@dataclass
class StyleBrief:
    """Configuration for generating a style/reference sheet."""
    theme: str
    age_level: str
    difficulty: str
    notes: str = ""
    reference_image: Optional[str] = None  # Base64 data URL if provided
    style: str = "bold-easy"  # Art style (zentangle, mandala, bold-easy, etc.)


class ColoringStyleGenerator:
    """
    Generate reference/style sheets for coloring books.

    Creates a unified style sheet showing 4-6 example elements that
    establish line weight, complexity, and visual language for the entire book.
    """

    def __init__(self, api_key: Optional[str] = None, draft_mode: bool = False):
        """
        Initialize the style generator.

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

        # Model selection for cost optimization:
        # - dall-e-2: Cheapest (~$0.02/image), use for drafts and simple generation
        # - gpt-image-1: More expensive, but better quality for production
        if draft_mode:
            self.cheap_model = "dall-e-2"
            self.image_model = "dall-e-2"  # Use dall-e-2 for everything in draft mode
            logger.info("Draft mode enabled - using dall-e-2 for all images")
        else:
            self.cheap_model = "dall-e-2"  # For generation without reference
            self.image_model = "gpt-image-1"  # For edit with reference image

        self.max_retries = 3
        self.initial_backoff = 30

        logger.info(f"ColoringStyleGenerator initialized with model: {self.image_model}")

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

    def _get_theme_guidelines(self, theme: str) -> str:
        """Get guidelines for a theme."""
        theme_lower = theme.lower()
        for key, guidelines in THEME_GUIDELINES.items():
            if key in theme_lower:
                return guidelines
        return THEME_GUIDELINES["custom"]

    def _get_difficulty_mod(self, difficulty: str) -> Dict[str, Any]:
        """Get difficulty modifier."""
        return DIFFICULTY_MODS.get(difficulty.lower(), DIFFICULTY_MODS["medium"])

    def _generate_concepts_with_llm(self, brief: StyleBrief, num_pages: int, exclusion_list: str = "") -> list:
        """
        Use LLM to generate diverse, unique concepts for coloring book pages.
        Each concept should be completely different from the others.

        Args:
            brief: StyleBrief with theme and specifications
            num_pages: Number of concepts to generate
            exclusion_list: Comma-separated list of subjects already used (to avoid)
        """
        try:
            from openai import OpenAI
            client = OpenAI()

            prompt = f"""Generate {num_pages} coloring page concepts for "{brief.theme}" theme.

CRITICAL: Each page MUST have a DIFFERENT primary subject.
- Page 1: butterfly, Page 2: ladybug, Page 3: dragonfly (GOOD - all different)
- Page 1: butterfly, Page 2: butterfly flying, Page 3: butterfly on flower (BAD - all butterflies!)

For "{brief.theme}", list {num_pages} DIFFERENT subjects, one per line.
Each line: [subject] [action/pose] [simple setting]

FORBIDDEN subjects (already used): {exclusion_list if exclusion_list else "None yet"}

REQUIREMENTS:
- Each concept must be a DIFFERENT subject/scene (not variations of the same thing)
- Each concept should be 5-15 words describing ONE clear main subject
- Concepts should be visually distinct from each other
- Good for {brief.age_level} age level coloring
- Suitable for {brief.difficulty} difficulty

BAD EXAMPLE (too similar):
1. Cupcake with frosting
2. Cupcake with sprinkles
3. Cupcake with cherry on top
(These are all cupcakes - TOO SIMILAR!)

GOOD EXAMPLE for "Food & Desserts" theme:
1. Birthday cake with candles and decorations
2. Ice cream sundae with toppings in tall glass
3. Stack of pancakes with berries and syrup
4. Large pizza with various toppings
5. Fruit basket overflowing with apples and grapes
6. Popcorn bucket at the movies
(Each is a DIFFERENT food item!)

Now generate {num_pages} unique concepts for "{brief.theme}":"""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.9  # Higher temperature for more diversity
            )

            # Parse the response
            content = response.choices[0].message.content
            lines = content.strip().split('\n')
            concepts = []
            for line in lines:
                # Remove numbering and clean up
                line = line.strip()
                if not line:
                    continue
                # Remove common prefixes like "1.", "1)", "- ", etc.
                import re
                cleaned = re.sub(r'^[\d]+[\.\)\-\s]+', '', line).strip()
                cleaned = re.sub(r'^[-\*\s]+', '', cleaned).strip()
                if cleaned and len(cleaned) > 5:
                    concepts.append(cleaned)

            # Validate uniqueness
            if not self._validate_unique_subjects(concepts):
                logger.warning("Generated concepts have duplicate subjects, regenerating...")
                # Try once more with stricter prompt
                concepts = self._generate_concepts_strict(brief, num_pages, exclusion_list)

            logger.info(f"LLM generated {len(concepts)} concepts for theme: {brief.theme}")
            return concepts

        except Exception as e:
            logger.warning(f"LLM concept generation error: {e}")
            raise

    def _extract_subject(self, concept: str) -> str:
        """Extract primary subject from concept string."""
        # Get the first 1-2 meaningful words (skip articles, adjectives)
        skip_words = {'a', 'an', 'the', 'large', 'small', 'big', 'tiny', 'cute', 'beautiful',
                      'majestic', 'friendly', 'happy', 'single', 'one', 'two', 'decorated'}
        words = concept.lower().split()
        for word in words:
            # Remove punctuation
            clean_word = ''.join(c for c in word if c.isalnum())
            if clean_word and clean_word not in skip_words and len(clean_word) > 2:
                return clean_word
        return words[0] if words else "unknown"

    def _validate_unique_subjects(self, concepts: list) -> bool:
        """Check that all concepts have different primary subjects."""
        subjects = [self._extract_subject(c) for c in concepts]
        unique_subjects = set(subjects)
        # Allow some overlap (80% unique is acceptable)
        uniqueness_ratio = len(unique_subjects) / len(subjects) if subjects else 0
        return uniqueness_ratio >= 0.8

    def _generate_concepts_strict(self, brief: StyleBrief, num_pages: int, exclusion_list: str = "") -> list:
        """Generate concepts with stricter uniqueness enforcement."""
        from openai import OpenAI
        client = OpenAI()

        prompt = f"""Generate {num_pages} coloring page concepts for "{brief.theme}".

STRICT UNIQUENESS RULE: Each line MUST start with a DIFFERENT noun.
NO repetition of any subject - each page shows a completely different thing.

Format: [unique subject noun] [action] [setting]

{f"DO NOT use these subjects (already used): {exclusion_list}" if exclusion_list else ""}

Generate exactly {num_pages} lines, one concept per line:"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.9
        )

        content = response.choices[0].message.content
        lines = content.strip().split('\n')
        concepts = []
        import re
        for line in lines:
            line = line.strip()
            if not line:
                continue
            cleaned = re.sub(r'^[\d]+[\.\)\-\s]+', '', line).strip()
            cleaned = re.sub(r'^[-\*\s]+', '', cleaned).strip()
            if cleaned and len(cleaned) > 5:
                concepts.append(cleaned)

        return concepts[:num_pages]

    def generate_reference_sheet(
        self,
        brief: StyleBrief,
        output_path: Optional[Path] = None
    ) -> Tuple[bool, Path]:
        """
        Generate a reference/style sheet for the coloring book.

        The reference sheet shows 4-6 example elements in a unified style,
        establishing the line weight, complexity, and visual language.

        Args:
            brief: StyleBrief with theme, age, difficulty, and notes
            output_path: Where to save the reference sheet

        Returns:
            Tuple of (success, output_path)
        """
        if output_path is None:
            output_path = Path("reference_sheet.png")

        # Get specifications
        age_specs = self._get_age_specs(brief.age_level)
        theme_guidelines = self._get_theme_guidelines(brief.theme)
        difficulty_mod = self._get_difficulty_mod(brief.difficulty)

        # Debug logging for style
        logger.info(f"=== STYLE DEBUG ===")
        logger.info(f"brief.style value: '{brief.style}'")
        logger.info(f"Available styles: {list(ART_STYLES.keys())}")

        art_style = ART_STYLES.get(brief.style, ART_STYLES["bold-easy"])

        logger.info(f"Resolved art_style: '{art_style[:50]}...'")
        logger.info(f"=== END STYLE DEBUG ===")

        # Build concise prompt (DALL-E limit is 1000 chars)
        # Only include essential info
        notes_str = f" Notes: {brief.notes[:100]}" if brief.notes else ""
        prompt = f"""Coloring book style sheet for "{brief.theme}" theme.

Draw 4-6 {brief.theme} items. {age_specs['line_weight']}. {age_specs['description']}.

Style: {art_style[:150]}

Requirements:
- BLACK LINES on WHITE only, no colors/gray
- Closed shapes for coloring
- No text/labels/watermarks
- 5% margin, nothing cropped
- Clean white background{notes_str}"""

        logger.info(f"Generating reference sheet: {brief.theme}, {brief.age_level}, {brief.difficulty}")

        # Generate the reference sheet
        for attempt in range(self.max_retries):
            try:
                # If reference image provided, use images.edit
                if brief.reference_image:
                    logger.info("Using reference image for style generation")
                    # Save reference image to temp file
                    import tempfile
                    if brief.reference_image.startswith('data:'):
                        base64_data = brief.reference_image.split(',', 1)[1]
                    else:
                        base64_data = brief.reference_image

                    temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                    temp_file.write(base64.b64decode(base64_data))
                    temp_file.close()

                    with open(temp_file.name, 'rb') as ref_file:
                        response = self.client.images.edit(
                            model=self.image_model,
                            image=[ref_file],
                            prompt=prompt,
                            size="1024x1024"  # Square for reference sheet (dall-e-2 compatible)
                        )

                    # Clean up temp file
                    os.unlink(temp_file.name)
                else:
                    # Use cheaper dall-e-2 for generation without reference
                    response = self.client.images.generate(
                        model=self.cheap_model,
                        prompt=prompt,
                        size="1024x1024",  # dall-e-2 only supports square
                        n=1
                        # Note: dall-e-2 doesn't support quality parameter
                    )

                # Save the result
                if response.data[0].b64_json:
                    self._save_image(response.data[0].b64_json, output_path)
                    logger.info("Reference sheet generated successfully")
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
                logger.error(f"Error generating reference sheet: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(5)
                else:
                    return False, output_path

        return False, output_path

    def generate_page_concepts(
        self,
        brief: StyleBrief,
        num_pages: int
    ) -> list:
        """
        Generate concept descriptions for each page in the coloring book.
        Uses LLM to create diverse, unique concepts for each page.

        Args:
            brief: StyleBrief with theme and specifications
            num_pages: Number of pages to generate concepts for

        Returns:
            List of concept strings for each page
        """
        # Try LLM-based generation first for better diversity
        try:
            llm_concepts = self._generate_concepts_with_llm(brief, num_pages)
            if llm_concepts and len(llm_concepts) >= num_pages:
                logger.info(f"Generated {len(llm_concepts)} unique concepts via LLM")
                return llm_concepts[:num_pages]
        except Exception as e:
            logger.warning(f"LLM concept generation failed, using fallback: {e}")

        # Fallback to static concepts
        theme_concepts = {
            "mandalas": [
                "Simple circular mandala with flower petals",
                "Mandala with geometric triangular patterns",
                "Nature-inspired mandala with leaves",
                "Mandala with star and diamond shapes",
                "Mandala with swirling spiral patterns",
                "Mandala with heart and love symbols",
                "Mandala with ocean wave patterns",
                "Mandala with sun and celestial elements",
                "Complex interlocking mandala design",
                "Mandala with butterfly wing patterns",
                "Mandala with peacock feather motifs",
                "Sacred geometry mandala pattern"
            ],
            "animals": [
                "Majestic lion portrait with detailed mane",
                "Elephant with decorative patterns",
                "Owl with intricate feather details",
                "Butterfly with symmetrical wing patterns",
                "Seahorse with scale textures",
                "Fox in forest setting",
                "Cat with mandala-style decorations",
                "Peacock displaying tail feathers",
                "Wolf howling at moon",
                "Hummingbird among flowers",
                "Turtle with shell patterns",
                "Deer with antler decorations"
            ],
            "nature": [
                "Rose bloom with detailed petals",
                "Sunflower with seeds and leaves",
                "Tree of life with branches and roots",
                "Garden scene with multiple flowers",
                "Tropical leaves arrangement",
                "Cherry blossom branch",
                "Lotus flower on water",
                "Wildflower meadow scene",
                "Mushrooms in forest floor",
                "Fern fronds pattern",
                "Succulent arrangement",
                "Autumn leaves falling"
            ],
            "fantasy": [
                "Majestic dragon portrait",
                "Fairy with detailed wings",
                "Unicorn in magical forest",
                "Phoenix rising from flames",
                "Mermaid among coral",
                "Castle in the clouds",
                "Wizard with magical staff",
                "Enchanted forest scene",
                "Griffin with spread wings",
                "Mystical crystal cave",
                "Enchanted garden gateway",
                "Dragon and knight scene"
            ],
            "food": [
                "Single decorated birthday cake with candles",
                "Ice cream sundae with toppings and cherry",
                "Stack of pancakes with berries and syrup",
                "Pizza with various toppings",
                "Basket of assorted fruits",
                "Candy jar filled with sweets",
                "Cupcake with elaborate frosting swirl",
                "Donut collection with different toppings",
                "Chocolate bar breaking apart",
                "Milkshake with whipped cream and straw",
                "Popcorn bucket overflowing",
                "Sushi platter arrangement",
                "Hamburger with all the fixings",
                "Pretzel with salt crystals",
                "Lollipop and candy cane arrangement",
                "Pie with lattice crust",
                "Cookie assortment on a plate",
                "Hot chocolate mug with marshmallows",
                "Waffle with fruit toppings",
                "Gingerbread house decorated",
                "Popsicle collection on sticks",
                "Macarons stacked in tower",
                "Cinnamon roll with icing drizzle",
                "Fruit tart with berries"
            ],
            "dessert": [
                "Elaborate wedding cake multi-tier",
                "Ice cream cone with multiple scoops",
                "Brownie stack with chocolate drizzle",
                "Cheesecake slice with strawberry",
                "Eclair with cream filling",
                "Jello mold with fruit",
                "Banana split with toppings",
                "Apple pie slice with ice cream",
                "Churros with chocolate sauce",
                "Tiramisu layered dessert",
                "Parfait in tall glass",
                "S'mores with melting chocolate"
            ],
            "aquatic": [
                "Sea turtle swimming through coral",
                "Octopus with curling tentacles",
                "School of tropical fish",
                "Jellyfish floating gracefully",
                "Whale breaching ocean surface",
                "Seahorse among seaweed",
                "Crab on sandy beach",
                "Dolphin jumping through waves",
                "Coral reef ecosystem scene",
                "Starfish collection on shore",
                "Manta ray gliding underwater",
                "Clownfish in anemone home"
            ]
        }

        # Find matching theme or use generic concepts
        theme_lower = brief.theme.lower()
        concepts = None
        for key, concept_list in theme_concepts.items():
            if key in theme_lower:
                concepts = concept_list
                break

        if concepts is None:
            # Generate generic concepts based on theme
            concepts = [f"{brief.theme} design {i+1}" for i in range(num_pages)]

        # Ensure we have enough concepts
        while len(concepts) < num_pages:
            concepts.extend(concepts[:num_pages - len(concepts)])

        return concepts[:num_pages]


def main():
    """Test the style generator."""
    generator = ColoringStyleGenerator()

    brief = StyleBrief(
        theme="Fantasy Dragons",
        age_level="teen",
        difficulty="medium",
        notes="Include both Western and Eastern dragon styles"
    )

    output_path = Path("test_reference_sheet.png")
    success, path = generator.generate_reference_sheet(brief, output_path)

    print(f"Generation {'succeeded' if success else 'failed'}: {path}")

    # Generate concepts
    concepts = generator.generate_page_concepts(brief, 12)
    print("\nGenerated page concepts:")
    for i, concept in enumerate(concepts, 1):
        print(f"  {i}. {concept}")


if __name__ == "__main__":
    main()
