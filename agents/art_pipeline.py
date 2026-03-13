"""
Art Generation Pipeline for Automated Children's Book Publishing Studio

This module provides a complete pipeline for generating character-consistent
illustrated children's books using OpenAI's image generation and editing APIs.

Key Features:
- Character sheet generation for reference consistency
- Scene illustration generation with character sheet references
- Vision-based QA checking for quality assurance
- Full pipeline orchestration with retry logic
- Rate limit handling with exponential backoff
"""

import os
import sys
import time
import base64
import logging
import requests
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import json

try:
    from openai import OpenAI, RateLimitError
except ImportError:
    print("Error: openai package not found. Install with: pip install openai")
    sys.exit(1)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CriticalImageFailure(Exception):
    """Raised when first image fails after all retries - abort pipeline to save costs."""
    pass


class ArtPipeline:
    """
    Manages the complete art generation pipeline for children's book illustrations.

    Uses OpenAI's image generation and editing APIs to create character-consistent
    illustrations with vision-based quality assurance.
    """

    # Default style only used when no style is provided
    DEFAULT_STYLE = "Soft watercolor children's book illustration with gentle colors and warm, friendly aesthetic. Character consistency across the full series: same face, same color, same eye shape, same outfit, same proportions, same silhouette, same world, same lighting language, same rendering style across every image."

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini", style: Optional[str] = None, eye_style: Optional[str] = None, reference_image: Optional[str] = None, qa_first_only: bool = True, hard_rules: Optional[str] = None):
        """
        Initialize the ArtPipeline.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY environment variable.
            model: Vision model to use for QA checks. Defaults to gpt-4o-mini.
            qa_first_only: If True, only QA the character sheet (first image) to save costs.
            style: Art style to use for all generations. If None, must be provided per-method call.
            eye_style: Specific eye style instructions for character consistency.
            reference_image: Base64 data URL of a reference image for character design.
            hard_rules: Strict rules that must be followed in ALL image generation (e.g., "NO ONE WEARS GREEN").

        Raises:
            ValueError: If no API key is provided and OPENAI_API_KEY env var is not set.
        """
        if api_key is None:
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                raise ValueError(
                    "No API key provided. Set OPENAI_API_KEY environment variable or "
                    "pass api_key parameter."
                )

        self.client = OpenAI(api_key=api_key)
        self.vision_model = model
        self.image_model = "gpt-image-1"  # OpenAI's newest image generation model
        self.style = style  # Store style at instance level
        self.eye_style = eye_style  # Store eye style for consistency
        self.reference_image = reference_image  # Store reference image for character design
        self.hard_rules = hard_rules  # Strict rules for ALL images (e.g., "NO GREEN CLOTHING")
        self.character_visual_guide = None  # Detailed description extracted from character sheet
        self.character_sheet_path = None  # Path to generated character sheet for scene references

        # QA thresholds
        self.max_retries = 3
        self.initial_backoff = 30  # seconds
        self.qa_first_only = qa_first_only  # Only QA character sheet to save costs

        # Analyze reference image if provided
        self.reference_features = None
        if reference_image:
            logger.info("Analyzing reference image for character features...")
            self.reference_features = self._analyze_reference_image(reference_image)
            if self.reference_features:
                logger.info(f"Extracted features: {self.reference_features[:200]}...")

        logger.info(f"ArtPipeline initialized with image model: {self.image_model}")
        if style:
            logger.info(f"Using art style: {style[:100]}...")
        if eye_style:
            logger.info(f"Using eye style: {eye_style[:100]}...")

    def _analyze_reference_image(self, reference_image: str) -> Optional[str]:
        """
        Analyze a reference image using GPT-4 Vision to extract facial features.

        Args:
            reference_image: Base64 data URL of the reference image

        Returns:
            String description of extracted features, or None if analysis fails
        """
        try:
            # Extract base64 data from data URL
            if reference_image.startswith('data:'):
                # Format: data:image/png;base64,<data>
                base64_data = reference_image.split(',', 1)[1]
                media_type = reference_image.split(';')[0].split(':')[1]
            else:
                base64_data = reference_image
                media_type = "image/png"

            analysis_prompt = """Analyze this person's facial features for use in children's book character design.
Provide a detailed but concise description covering:

*** MOST IMPORTANT - STATE FIRST ***
1. SKIN TONE & ETHNICITY: Be VERY specific (e.g., "dark brown skin / Black/African features", "light brown skin / South Asian features", "fair/pale skin / Caucasian features", "tan/golden skin / Latino features", "warm brown skin / Middle Eastern features"). This MUST be stated clearly!

2. FACE SHAPE: (oval, round, square, heart, oblong, diamond, etc.)
3. EYE SHAPE: (almond, round, hooded, monolid, upturned, downturned, etc.)
4. EYE COLOR: (specific color)
5. EYE SIZE: (large, medium, small relative to face)
6. NOSE SHAPE: (button, straight, curved, wide, narrow, upturned, etc.)
7. NOSE SIZE: (small, medium, prominent)
8. LIP SHAPE: (full, thin, heart-shaped, wide, etc.)
9. HAIR COLOR: (specific color/tones)
10. HAIR TEXTURE: (straight, wavy, curly, coily, kinky, etc.)
11. HAIR STYLE: (length and how it's worn)
12. DISTINCTIVE FEATURES: (dimples, freckles, birthmarks, etc.)

Format as a single paragraph description suitable for an artist. START WITH SKIN TONE/ETHNICITY as the first thing mentioned! Example: "Character based on reference: Dark brown skin with African features, round face shape..." """

            for attempt in range(3):
                try:
                    response = self.client.chat.completions.create(
                        model=self.vision_model,
                        max_tokens=500,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{media_type};base64,{base64_data}"
                                        }
                                    },
                                    {
                                        "type": "text",
                                        "text": analysis_prompt
                                    }
                                ]
                            }
                        ]
                    )

                    features = response.choices[0].message.content
                    logger.info("Reference image analysis complete")
                    return features

                except RateLimitError:
                    if attempt < 2:
                        wait_time = 30 * (attempt + 1)
                        logger.warning(f"Rate limited analyzing reference. Waiting {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error("Rate limit exceeded for reference image analysis")
                        return None

        except Exception as e:
            logger.error(f"Error analyzing reference image: {e}")
            return None

    def _analyze_character_sheet(self, char_sheet_path: Path) -> Optional[str]:
        """
        Analyze a generated character sheet to extract detailed visual description.
        This description is then used in all scene illustrations for consistency.

        Args:
            char_sheet_path: Path to the character sheet image

        Returns:
            Detailed character description string, or None if analysis fails
        """
        try:
            with open(char_sheet_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            analysis_prompt = """Analyze this character sheet and create a CHARACTER DNA description that will be copy-pasted into every subsequent image prompt to ensure PERFECT consistency.

Extract and describe EVERY detail with EXACT specifications. Use descriptive, specific terms (not vague ones).

OUTPUT FORMAT - Use this exact structure:

CHARACTER DNA:

SKIN: [Use descriptive terms like "warm caramel-brown" or "peachy cream" or "deep mahogany" - NOT just "brown" or "light"]

FACE SHAPE: [round/oval/square/heart-shaped with specific details about proportions]

EYES:
- Shape: [almond/round/wide-set/hooded - be specific]
- Size: [large/medium relative to face]
- Color: [specific shade like "warm chocolate brown" or "bright emerald green"]
- Style: [cartoon dot eyes/detailed with whites and iris/anime style - CRITICAL for consistency]
- Highlights: [describe the white highlight dots in the eyes - position, size, number - CRITICAL for consistency]

NOSE: [button/straight/upturned - specific shape AND size]

HAIR:
- Color: [specific like "jet black" or "warm copper-orange" - NOT just "brown"]
- Texture: [straight/wavy/curly/coily]
- Style: [how it's worn - pigtails/loose/braided/short spiky]
- Length: [shoulder-length/short/long]

BODY: [age-appropriate build and proportions]

CLOTHING:
- Top: [exact item with specific color]
- Bottom: [exact item with specific color]
- Footwear: [exact item with specific color]
- Accessories: [any items that should always be present]

DISTINGUISHING FEATURES: [freckles/dimples/birthmarks/signature items]

ART STYLE: [watercolor/digital/flat vector - describe the illustration style]

Keep descriptions concise but EXACT. Every detail you specify will be used to maintain consistency across all book illustrations."""

            for attempt in range(3):
                try:
                    response = self.client.chat.completions.create(
                        model=self.vision_model,
                        max_tokens=800,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/png;base64,{image_data}"
                                        }
                                    },
                                    {
                                        "type": "text",
                                        "text": analysis_prompt
                                    }
                                ]
                            }
                        ]
                    )

                    description = response.choices[0].message.content
                    logger.info(f"Character sheet analysis complete: {description[:200]}...")
                    return description

                except RateLimitError:
                    if attempt < 2:
                        wait_time = 30 * (attempt + 1)
                        logger.warning(f"Rate limited analyzing character sheet. Waiting {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error("Rate limit exceeded for character sheet analysis")
                        return None

        except Exception as e:
            logger.error(f"Error analyzing character sheet: {e}")
            return None

    def _download_image(self, url: str, output_path: Path) -> None:
        """Download image from URL and save to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(response.content)
        logger.info(f"Image downloaded to {output_path}")

    def _image_to_base64_url(self, image_path: Path) -> str:
        """Convert image file to base64 data URL for API input."""
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        return f"data:image/png;base64,{image_data}"

    def _prepare_reference_image_for_edit(self, image_source: str) -> Path:
        """
        Prepare reference image for images.edit API by saving to temp file.

        Args:
            image_source: Either a base64 data URL or file path

        Returns:
            Path to temporary image file
        """
        import tempfile

        if image_source.startswith('data:'):
            # Extract base64 data from data URL and save to temp file
            base64_data = image_source.split(',', 1)[1]
            image_bytes = base64.b64decode(base64_data)

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            temp_file.write(image_bytes)
            temp_file.close()
            return Path(temp_file.name)
        elif Path(image_source).exists():
            return Path(image_source)
        else:
            raise ValueError(f"Invalid image source: {image_source}")

    def _save_image(self, image_data: str, output_path: Path) -> None:
        """
        Save base64-encoded image data to file.

        Args:
            image_data: Base64-encoded image data
            output_path: Path where image should be saved
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image_bytes = base64.b64decode(image_data)
        with open(output_path, 'wb') as f:
            f.write(image_bytes)
        logger.info(f"Image saved to {output_path}")

    def _exponential_backoff(self, attempt: int) -> None:
        """
        Apply exponential backoff for rate limiting.

        Args:
            attempt: Attempt number (0-indexed)
        """
        wait_time = self.initial_backoff * (2 ** attempt)
        logger.warning(f"Rate limited. Waiting {wait_time} seconds before retry...")
        time.sleep(wait_time)

    def _add_hard_rules(self, prompt: str) -> str:
        """
        Add hard rules to prompt if any are set.

        Args:
            prompt: Original prompt text

        Returns:
            Prompt with hard rules prepended if they exist
        """
        if self.hard_rules and self.hard_rules.strip():
            rules_block = (
                f"=== STRICT RULES - MUST FOLLOW ===\n"
                f"{self.hard_rules.strip()}\n"
                f"=== END STRICT RULES ===\n\n"
            )
            return rules_block + prompt
        return prompt

    def _add_eye_safety_instructions(self, prompt: str, eye_style: str = None) -> str:
        """
        Add critical eye consistency instructions to prompt.

        Args:
            prompt: Original prompt text
            eye_style: Specific eye style description. If None, uses generic consistency instruction.

        Returns:
            Prompt with eye safety instructions prepended
        """
        # Always include the eye highlight requirement - this is what QA checks for
        highlight_requirement = (
            "Eyes must have large, round irises with TWO small bright white highlight dots "
            "(one larger, one smaller) to show life and expression. Eyes should NOT be solid black."
        )

        if eye_style:
            eye_instructions = f"CRITICAL — CHARACTER EYES: {eye_style}. {highlight_requirement}\n\n"
        else:
            # Generic instruction to match character sheet with highlight requirement
            eye_instructions = (
                f"CRITICAL — CHARACTER EYES: Must match EXACTLY the same eye style "
                f"as shown in the character reference sheet. Same shape, same color, "
                f"same level of detail. {highlight_requirement}\n\n"
            )
        return eye_instructions + prompt

    def extract_recurring_characters(self, scenes: List[dict], main_character: str) -> dict:
        """
        Analyze scenes to identify recurring characters (appear in 2+ scenes).

        Args:
            scenes: List of scene dictionaries with 'illustration_prompt' keys
            main_character: Name of the main character (already has a sheet)

        Returns:
            Dictionary with character info: {
                'character_name': {
                    'scenes': [1, 3, 5],  # scene numbers where character appears
                    'description': 'physical description from scenes'
                }
            }
        """
        if not scenes:
            return {}

        try:
            # Combine all scene prompts for analysis
            scene_texts = []
            for i, scene in enumerate(scenes):
                prompt = scene.get('illustration_prompt', '')
                text = ' '.join(scene.get('text', []))
                scene_texts.append(f"Scene {i+1}: {prompt} | Text: {text}")

            combined_scenes = '\n'.join(scene_texts)

            analysis_prompt = f"""Analyze these children's book scenes and identify ALL characters (people/animals) that appear in 2 or more scenes.

The MAIN character is "{main_character}" - DO NOT include them (they already have a character sheet).

For each RECURRING character (appears 2+ times), provide:
1. Character name/identifier
2. List of scene numbers where they appear
3. A detailed physical description compiled from all their appearances

SCENES:
{combined_scenes}

Return your analysis in this EXACT format (one character per line):
CHARACTER: [name] | SCENES: [comma-separated numbers] | DESCRIPTION: [detailed physical description]

If no recurring secondary characters exist, return: NONE

IMPORTANT: Only include characters that appear in AT LEAST 2 different scenes. Skip one-time appearances."""

            response = self.client.responses.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": analysis_prompt}]
            )

            result_text = response.content[0].text.strip()

            if "NONE" in result_text.upper():
                logger.info("No recurring secondary characters found")
                return {}

            # Parse the response
            characters = {}
            for line in result_text.split('\n'):
                if 'CHARACTER:' in line and 'SCENES:' in line and 'DESCRIPTION:' in line:
                    try:
                        # Parse: CHARACTER: name | SCENES: 1,3,5 | DESCRIPTION: ...
                        parts = line.split('|')
                        name = parts[0].replace('CHARACTER:', '').strip()
                        scenes_str = parts[1].replace('SCENES:', '').strip()
                        description = parts[2].replace('DESCRIPTION:', '').strip()

                        # Skip if it's the main character
                        if main_character.lower() in name.lower():
                            continue

                        scene_nums = [int(s.strip()) for s in scenes_str.split(',') if s.strip().isdigit()]

                        if len(scene_nums) >= 2:  # Only if appears in 2+ scenes
                            characters[name] = {
                                'scenes': scene_nums,
                                'description': description
                            }
                            logger.info(f"Found recurring character: {name} in scenes {scene_nums}")
                    except Exception as e:
                        logger.warning(f"Failed to parse character line: {line}, error: {e}")
                        continue

            return characters

        except Exception as e:
            logger.error(f"Error extracting recurring characters: {e}")
            return {}

    def generate_all_character_sheets(
        self,
        main_character_desc: str,
        main_character_name: str,
        recurring_characters: dict,
        output_dir: Path,
        style: str
    ) -> dict:
        """
        Generate character sheets for main character and all recurring characters.

        Args:
            main_character_desc: Description of main character
            main_character_name: Name of main character
            recurring_characters: Dict from extract_recurring_characters()
            output_dir: Base output directory
            style: Art style for illustrations

        Returns:
            Dictionary mapping character names to their sheet paths
        """
        char_sheets_dir = output_dir / "character_sheets"
        char_sheets_dir.mkdir(parents=True, exist_ok=True)

        sheets = {}

        # Generate main character sheet
        main_sheet_path = char_sheets_dir / f"{main_character_name}_sheet.png"
        if main_sheet_path.exists():
            logger.info(f"Using existing main character sheet: {main_sheet_path}")
            sheets[main_character_name] = main_sheet_path
            # Analyze for visual guide
            if not self.character_visual_guide:
                self.character_visual_guide = self._analyze_character_sheet(main_sheet_path)
        else:
            logger.info(f"Generating main character sheet: {main_character_name}")
            try:
                _, sheet_path = self.generate_character_sheet(
                    main_character_desc,
                    main_sheet_path,
                    style=style
                )
                sheets[main_character_name] = sheet_path
            except Exception as e:
                logger.error(f"Failed to generate main character sheet: {e}")

        # Generate sheets for recurring characters
        for char_name, char_info in recurring_characters.items():
            safe_name = "".join(c if c.isalnum() else "_" for c in char_name)
            sheet_path = char_sheets_dir / f"{safe_name}_sheet.png"

            if sheet_path.exists():
                logger.info(f"Using existing character sheet for {char_name}: {sheet_path}")
                sheets[char_name] = sheet_path
            else:
                logger.info(f"Generating character sheet for: {char_name} (appears in scenes {char_info['scenes']})")
                try:
                    # Build description for secondary character sheet
                    char_desc = f"""Secondary character for children's book:
Name: {char_name}
Description: {char_info['description']}

This character appears alongside the main character in multiple scenes.
Create a character sheet showing this character in various poses and expressions,
maintaining the same art style as the main book."""

                    _, sheet_path = self.generate_character_sheet(
                        char_desc,
                        sheet_path,
                        style=style
                    )
                    sheets[char_name] = sheet_path
                except Exception as e:
                    logger.error(f"Failed to generate character sheet for {char_name}: {e}")

        return sheets

    def generate_character_sheet(
        self,
        character_desc: str,
        output_path: Optional[Path] = None,
        style: Optional[str] = None,
        guidance: Optional[str] = None,
        guidance_reference: Optional[str] = None
    ) -> Tuple[str, Path]:
        """
        Generate a character reference sheet with multiple poses and expressions.

        Uses images.generate() to create a comprehensive character sheet showing
        the character in various poses and emotional expressions.

        Args:
            character_desc: Description of the character to generate
            output_path: Where to save the character sheet. If None, uses default location.
            style: Art style for the illustration. If None, uses instance style or default.

        Returns:
            Tuple of (image_data as base64, saved_path)

        Raises:
            Exception: If generation fails after retries
        """
        if output_path is None:
            output_path = Path.home() / "books_output" / "character_sheets" / "character.png"

        # Use provided style, fall back to instance style, then default
        art_style = style or self.style or self.DEFAULT_STYLE

        # Build character DNA - the detailed description that stays identical across all prompts
        # Reference features from analyzed image take priority
        character_dna = ""
        if self.reference_features:
            character_dna = (
                f"CHARACTER DNA (preserve exactly in all poses):\n"
                f"{self.reference_features}\n"
            )

        # Add the character description
        character_dna += f"\n{character_desc}\n"

        # Build guidance section if provided
        guidance_section = ""
        if guidance:
            guidance_section = f"""
STYLE REFINEMENTS (Apply these adjustments to the character):
{guidance.strip()}
"""
            logger.info(f"Applying regeneration guidance: {guidance[:100]}...")

        # DEBUG: Log what's being used
        logger.info(f"Character sheet generation - Reference features present: {bool(self.reference_features)}")
        if self.reference_features:
            logger.info(f"Reference features: {self.reference_features[:300]}...")

        # Build prompt following optimal order: Style → Character → Guidance → Layout → Constraints
        prompt = f"""Children's book illustration character reference sheet.

ART STYLE: {art_style}

{character_dna}
{guidance_section}
LAYOUT: Create a 4-panel character reference sheet on a clean white background:
- Top left: Full body frontal view with neutral expression
- Top right: Side profile view showing face and hair details
- Bottom left: 3/4 view with happy smiling expression
- Bottom right: Back view showing hair and clothing from behind

CRITICAL CONSISTENCY REQUIREMENTS:
- All 4 panels must show the EXACT SAME character
- Face shape must be IDENTICAL in all views (same roundness/angles)
- Eye shape, size, and color must be IDENTICAL
- EYES MUST have large round irises with TWO small bright white highlight dots (one larger, one smaller) - NOT solid black eyes
- Nose shape and size must be IDENTICAL
- Skin tone must be IDENTICAL (same exact shade)
- Hair color, length, style, and texture must be IDENTICAL
- Clothing colors and details must be IDENTICAL
- Body proportions must be consistent across all views

CONSTRAINTS:
- Uniform panel sizes with clear separation
- Simple solid white or light gray background
- NO text, labels, words, or writing of any kind
- Character is the only subject - no other characters or distracting elements
- Consistent lighting direction across all panels"""

        # Inject hard rules at the top of the prompt if they exist
        prompt = self._add_hard_rules(prompt)

        logger.info(f"Generating character sheet: {character_desc[:50]}...")

        # Use guidance_reference if provided, otherwise fall back to original reference
        active_reference = guidance_reference or self.reference_image

        attempt = 0
        while attempt < self.max_retries:
            try:
                # Generate character sheet - use images.edit if reference image provided
                if active_reference:
                    logger.info("Using images.edit with reference image for character sheet")
                    ref_path = self._prepare_reference_image_for_edit(active_reference)
                    # Prepend reference image instruction following best practices
                    ref_prompt = f"""REFERENCE IMAGE: The person in the attached image is the basis for this character.
Preserve their EXACT features in the illustrated character:
- EXACT face shape (same proportions and angles)
- EXACT eye shape, size, and color
- EXACT nose shape and size
- EXACT skin tone (same shade, do not lighten or darken)
- EXACT hair color, texture, and style

{prompt}"""
                    with open(ref_path, 'rb') as ref_file:
                        response = self.client.images.edit(
                            model=self.image_model,
                            image=[ref_file],  # Pass as list of file objects
                            prompt=ref_prompt,
                            size="1536x1024"  # Landscape for character sheet
                        )
                else:
                    # No reference image - use generate
                    logger.info("Using images.generate (no reference image)")
                    response = self.client.images.generate(
                        model=self.image_model,
                        prompt=prompt,
                        size="1536x1024",  # Landscape for character sheet
                        n=1,
                        quality="medium"
                    )

                # gpt-image-1 returns base64 data
                if response.data[0].b64_json:
                    self._save_image(response.data[0].b64_json, output_path)
                elif response.data[0].url:
                    self._download_image(response.data[0].url, output_path)
                logger.info("Character sheet generated successfully")

                # Store character sheet path for scene generation
                self.character_sheet_path = output_path

                # Analyze the character sheet to extract detailed visual guide
                logger.info("Analyzing character sheet for visual consistency...")
                self.character_visual_guide = self._analyze_character_sheet(output_path)
                if self.character_visual_guide:
                    logger.info("Character visual guide extracted successfully")

                return None, output_path

            except RateLimitError:
                if attempt < self.max_retries - 1:
                    self._exponential_backoff(attempt)
                    attempt += 1
                else:
                    raise CriticalImageFailure("Character sheet generation failed after 3 retries. Aborting pipeline to save costs.")
            except Exception as e:
                logger.error(f"Error generating character sheet: {e}")
                if attempt < self.max_retries - 1:
                    attempt += 1
                    time.sleep(5)
                else:
                    raise CriticalImageFailure(f"Character sheet generation failed after 3 retries: {e}. Aborting pipeline to save costs.")

        raise CriticalImageFailure("Character sheet generation failed after 3 retries. Aborting pipeline to save costs.")

    def generate_illustration(
        self,
        scene_description: str,
        char_sheet_path: Path,
        illustration_type: str = "spread",
        output_path: Optional[Path] = None,
        style: Optional[str] = None,
        additional_references: Optional[List[Path]] = None
    ) -> Tuple[str, Path]:
        """
        Generate a single illustration with character consistency.

        Uses images.edit() with the character sheet as reference to ensure
        the generated character maintains consistency with the reference.

        Args:
            scene_description: Description of the scene to illustrate
            char_sheet_path: Path to character sheet for reference
            illustration_type: "spread", "cover", or "back_cover"
            output_path: Where to save the illustration
            style: Art style for the illustration. If None, uses instance style or default.
            additional_references: Optional list of additional reference image paths

        Returns:
            Tuple of (image_data as base64, saved_path)

        Raises:
            FileNotFoundError: If character sheet path doesn't exist
            Exception: If generation fails after retries
        """
        if additional_references is None:
            additional_references = []
        if not char_sheet_path.exists():
            raise FileNotFoundError(f"Character sheet not found: {char_sheet_path}")

        if output_path is None:
            output_path = Path.home() / "books_output" / "spreads" / f"spread_{int(time.time())}.png"

        # Determine size based on type (gpt-image-1 supports various sizes)
        if illustration_type == "cover":
            size = "1024x1536"  # Portrait for cover
        elif illustration_type == "back_cover":
            size = "1024x1536"
        else:
            size = "1536x1024"  # Landscape for spreads

        # Use provided style, fall back to instance style, then default
        art_style = style or self.style or self.DEFAULT_STYLE

        # Build character DNA from visual guide (copy-paste identical in every prompt)
        character_dna = ""
        if self.character_visual_guide:
            logger.info(f"Using character visual guide for {illustration_type}: {self.character_visual_guide[:200]}...")
            character_dna = f"CHARACTER DNA (must preserve exactly):\n{self.character_visual_guide}\n"
        elif self.reference_features:
            character_dna = f"CHARACTER DNA (must preserve exactly):\n{self.reference_features}\n"
        else:
            logger.warning(f"NO character visual guide available for {illustration_type}!")

        # Build prompt following optimal order: Style → Scene → Character → Action → Constraints
        if illustration_type == "back_cover":
            prompt = f"""Children's book illustration - back cover design.

ART STYLE: {art_style}

SCENE: {scene_description}

This is the back cover. Show a beautiful landscape or scene setting that complements the story.
Focus on the environment, mood, and atmospheric design elements.

CONSTRAINTS:
- NO text, words, letters, numbers, titles, captions, or writing of any kind
- NO characters unless specifically requested in the scene description
- Maintain the same art style as the rest of the book
- Create a cohesive, peaceful background suitable for back cover text overlay"""

        else:
            prompt = f"""Children's book illustration for interior page.

ART STYLE: {art_style}

SCENE/BACKGROUND: {scene_description}

{character_dna}

CRITICAL CONSISTENCY REQUIREMENTS - Character must match reference exactly:
- Face shape: Preserve EXACT same shape (same roundness, same proportions)
- Eyes: IDENTICAL shape, size, color, and style as reference
- EYES MUST have large round irises with TWO small bright white highlight dots (one larger, one smaller) - NOT solid black eyes
- Nose: IDENTICAL shape and size as reference
- Skin tone: EXACT same shade as reference (do not lighten or darken)
- Hair: IDENTICAL color, length, style, and texture as reference
- Clothing: Same outfit with same colors as reference
- Body proportions: Consistent with reference

CONSTRAINTS:
- Change ONLY the pose, expression, and scene - NOT the character's features
- NO text, words, letters, numbers, or writing of any kind in the image
- Character should be the clear focal point
- Maintain consistent art style throughout"""

        # Inject hard rules at the top of the prompt if they exist
        prompt = self._add_hard_rules(prompt)

        logger.info(f"Generating {illustration_type}: {scene_description[:50]}...")

        attempt = 0
        while attempt < self.max_retries:
            try:
                # Use images.edit with character sheet as reference for consistency
                logger.info(f"Using images.edit with character sheet for {illustration_type}")
                # Prepend character reference instruction
                ref_prompt = f"""CHARACTER REFERENCE: The attached image shows the character that must appear in this scene.

CRITICAL - Preserve these features EXACTLY from the reference:
- Face shape: Same exact proportions
- Eyes: Identical shape, size, and color
- Nose: Same shape and size
- Skin tone: Exact same shade
- Hair: Same color, style, length, and texture
- Clothing: Same outfit and colors
- Body proportions: Consistent with reference

{prompt}"""
                # Build list of image files - character sheet first, then additional refs
                image_files = []
                char_file = open(char_sheet_path, 'rb')
                image_files.append(char_file)

                # Add additional reference files
                extra_files = []
                for extra_ref in additional_references:
                    if extra_ref.exists():
                        f = open(extra_ref, 'rb')
                        extra_files.append(f)
                        image_files.append(f)

                if extra_files:
                    ref_prompt += f"\n\n*** ADDITIONAL STYLE REFERENCES ***\nUse the {len(extra_files)} additional reference images for style consistency."

                try:
                    response = self.client.images.edit(
                        model=self.image_model,
                        image=image_files,  # Pass as list of file objects
                        prompt=ref_prompt,
                        size=size
                    )
                finally:
                    # Close all files
                    char_file.close()
                    for f in extra_files:
                        f.close()

                # gpt-image-1 returns base64 data
                if response.data[0].b64_json:
                    self._save_image(response.data[0].b64_json, output_path)
                elif response.data[0].url:
                    self._download_image(response.data[0].url, output_path)
                logger.info(f"{illustration_type.capitalize()} generated successfully")
                return None, output_path

            except RateLimitError:
                if attempt < self.max_retries:
                    self._exponential_backoff(attempt)
                    attempt += 1
                else:
                    raise Exception(f"{illustration_type} generation failed after max retries")
            except Exception as e:
                logger.error(f"Error generating {illustration_type}: {e}")
                if attempt < self.max_retries:
                    attempt += 1
                    time.sleep(5)
                else:
                    raise

        raise Exception(f"{illustration_type} generation failed")

    def qa_check(
        self,
        image_path: Path,
        expected_description: str
    ) -> Tuple[bool, str]:
        """
        Perform vision-based quality assurance check on generated image.

        Checks for:
        - Character eyes have white highlights (#1 production issue)
        - Character matches expected description
        - No unwanted text or watermarks
        - Overall composition and artistic quality

        Args:
            image_path: Path to image to check
            expected_description: What the image should contain

        Returns:
            Tuple of (pass/fail boolean, reason string)
        """
        if not image_path.exists():
            return False, f"Image file not found: {image_path}"

        # Read image and encode as base64
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        qa_prompt = (
            f"You are a quality assurance inspector for a children's book publishing system. "
            f"Review this illustration and check the following:\n\n"
            f"1. CHARACTER EYES (CRITICAL): Do all character eyes have large, round irises with "
            f"TWO small bright white highlight dots? Eyes should NOT be solid black. "
            f"Flag as FAIL if eyes are missing highlights.\n"
            f"2. CHARACTER CONSISTENCY: Does the character match this description: {expected_description}\n"
            f"3. TEXT/WATERMARKS: Are there any unwanted text, watermarks, or logos?\n"
            f"4. OVERALL QUALITY: Is the image well-composed and age-appropriate for children?\n\n"
            f"Respond in this exact format:\n"
            f"EYES: [PASS/FAIL] - [reason]\n"
            f"CHARACTER: [PASS/FAIL] - [reason]\n"
            f"TEXT: [PASS/FAIL] - [reason]\n"
            f"QUALITY: [PASS/FAIL] - [reason]\n"
            f"OVERALL: [PASS/FAIL] - [summary]"
        )

        try:
            # Use OpenAI's vision API format (gpt-4-turbo or gpt-4o)
            response = self.client.chat.completions.create(
                model=self.vision_model,
                max_tokens=500,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_data}"
                                }
                            },
                            {
                                "type": "text",
                                "text": qa_prompt
                            }
                        ]
                    }
                ]
            )

            qa_result = response.choices[0].message.content
            logger.info(f"QA Check Result:\n{qa_result}")

            # Check if overall result is PASS or FAIL
            overall_pass = "OVERALL: PASS" in qa_result.upper()

            return overall_pass, qa_result

        except Exception as e:
            logger.error(f"Error during QA check: {e}")
            return False, f"QA check failed with error: {str(e)}"

    def fix_image(
        self,
        image_name: str,
        char_sheet_path: Path,
        scene_description: str,
        illustration_type: str = "spread",
        output_dir: Optional[Path] = None,
        style: Optional[str] = None,
        additional_references: Optional[List[Path]] = None,
        skip_qa: bool = True
    ) -> Tuple[bool, str]:
        """
        Regenerate a single image with optional QA check.

        Args:
            image_name: Name of the image to regenerate
            char_sheet_path: Path to character sheet
            scene_description: Scene description for regeneration
            illustration_type: Type of illustration
            output_dir: Directory to save output
            style: Art style for the illustration. If None, uses instance style or default.
            additional_references: Optional list of additional reference image paths
            skip_qa: If True, skip QA check (for user-directed regeneration)

        Returns:
            Tuple of (success boolean, path_or_error_message)
        """
        if output_dir is None:
            output_dir = Path.home() / "books_output"

        # Determine output path based on illustration type
        if illustration_type == "spread":
            output_path = output_dir / "art" / image_name
        elif illustration_type == "cover":
            output_path = output_dir / "art" / "cover.png"
        else:
            output_path = output_dir / "art" / image_name

        if additional_references is None:
            additional_references = []

        logger.info(f"Regenerating image: {image_name} with {len(additional_references)} additional references")

        try:
            _, saved_path = self.generate_illustration(
                scene_description,
                char_sheet_path,
                illustration_type,
                output_path,
                style=style,
                additional_references=additional_references
            )

            # For user-directed regeneration, skip QA - trust their judgment
            if skip_qa:
                logger.info(f"Image regenerated successfully (QA skipped): {image_name}")
                return True, str(saved_path)

            # Run QA if requested
            passed, qa_result = self.qa_check(saved_path, scene_description)
            if passed:
                logger.info(f"Image regenerated and passed QA: {image_name}")
                return True, str(saved_path)
            else:
                # For user-directed regeneration, still return success even if QA fails
                logger.warning(f"Regenerated image has QA warnings (returning success anyway): {image_name}")
                return True, str(saved_path)

        except Exception as e:
            logger.error(f"Error fixing image {image_name}: {e}")
            return False, str(e)

    def generate_all(
        self,
        story_package: Dict,
        output_dir: Optional[Path] = None,
        style: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Generate complete illustrated book from story package.

        Full pipeline: character sheet → cover → 12 spreads → back cover
        Includes QA checking and auto-regeneration on failures (up to 3 retries).
        Skips existing files for resume capability.

        Args:
            story_package: Dictionary containing:
                - "character_description": str - Character description
                - "character_name": str - Character name
                - "title": str - Book title
                - "cover_scene": str - Cover illustration description
                - "spreads": List[str] - 12 scene descriptions (one per spread)
                - "back_cover_scene": str - Back cover description
                - "art_style": str (optional) - Art style for illustrations
            output_dir: Directory to save all output files
            style: Art style override. If None, uses story_package["art_style"] or instance style.

        Returns:
            Dictionary with generation results:
                - "success": bool
                - "character_sheet": Path
                - "cover": Path
                - "spreads": List[Path]
                - "back_cover": Path
                - "failed_images": List[str]
                - "qa_results": Dict
        """
        # Determine art style: method param > story_package > instance > default
        art_style = style or story_package.get("art_style") or self.style or self.DEFAULT_STYLE
        logger.info(f"Using art style: {art_style[:100]}...")
        if output_dir is None:
            output_dir = Path.home() / "books_output"

        output_dir.mkdir(parents=True, exist_ok=True)

        results = {
            "success": False,
            "character_sheet": None,
            "cover": None,
            "spreads": [],
            "back_cover": None,
            "failed_images": [],
            "qa_results": {}
        }

        try:
            logger.info(f"Starting book generation: {story_package.get('title', 'Untitled')}")

            # Step 1: Generate character sheet
            char_sheet_path = output_dir / "character_sheets" / f"{story_package['character_name']}_sheet.png"

            if char_sheet_path.exists():
                logger.info(f"Using existing character sheet: {char_sheet_path}")
                results["character_sheet"] = char_sheet_path
                # Analyze existing character sheet for visual consistency
                if not self.character_visual_guide:
                    logger.info("Analyzing existing character sheet for visual consistency...")
                    self.character_visual_guide = self._analyze_character_sheet(char_sheet_path)
                    if self.character_visual_guide:
                        logger.info("Character visual guide extracted successfully")
            else:
                logger.info("Step 1/3: Generating character sheet...")
                try:
                    _, char_sheet_path = self.generate_character_sheet(
                        story_package["character_description"],
                        char_sheet_path,
                        style=art_style
                    )
                    results["character_sheet"] = char_sheet_path
                except Exception as e:
                    logger.error(f"Failed to generate character sheet: {e}")
                    return results

            # Step 2: Generate cover
            cover_path = output_dir / "cover.png"
            if cover_path.exists():
                logger.info(f"Using existing cover: {cover_path}")
                results["cover"] = cover_path
            else:
                logger.info("Step 2/3: Generating cover...")
                try:
                    _, cover_path = self.generate_illustration(
                        story_package["cover_scene"],
                        char_sheet_path,
                        illustration_type="cover",
                        output_path=cover_path,
                        style=art_style
                    )

                    # Skip QA on cover when qa_first_only is enabled (saves cost)
                    if self.qa_first_only:
                        results["cover"] = cover_path
                        logger.info("Cover generated (QA skipped - qa_first_only mode)")
                    else:
                        passed, qa_result = self.qa_check(cover_path, story_package["cover_scene"])
                        results["qa_results"]["cover"] = {
                            "passed": passed,
                            "result": qa_result
                        }

                        if not passed:
                            results["failed_images"].append("cover")
                        else:
                            results["cover"] = cover_path
                            logger.info("Cover passed QA")

                except Exception as e:
                    logger.error(f"Failed to generate cover: {e}")
                    results["failed_images"].append("cover")

            # Step 3: Generate 12 spreads
            logger.info("Step 3/3: Generating spreads...")
            spreads_dir = output_dir / "spreads"
            spreads_dir.mkdir(parents=True, exist_ok=True)

            spreads = story_package.get("spreads", [])
            for i, spread_description in enumerate(spreads[:12], 1):
                spread_name = f"spread_{i:02d}.png"
                spread_path = spreads_dir / spread_name

                if spread_path.exists():
                    logger.info(f"Using existing spread {i}: {spread_name}")
                    results["spreads"].append(spread_path)
                    continue

                logger.info(f"Generating spread {i}/12...")

                retry_count = 0
                while retry_count < self.max_retries:
                    try:
                        _, spread_path = self.generate_illustration(
                            spread_description,
                            char_sheet_path,
                            illustration_type="spread",
                            output_path=spread_path,
                            style=art_style
                        )

                        # Skip QA on spreads when qa_first_only is enabled (saves cost)
                        if self.qa_first_only:
                            results["spreads"].append(spread_path)
                            logger.info(f"Spread {i} generated (QA skipped - qa_first_only mode)")
                            break

                        passed, qa_result = self.qa_check(
                            spread_path,
                            spread_description
                        )
                        results["qa_results"][spread_name] = {
                            "passed": passed,
                            "result": qa_result
                        }

                        if passed:
                            results["spreads"].append(spread_path)
                            logger.info(f"Spread {i} passed QA")
                            break
                        else:
                            logger.warning(f"Spread {i} failed QA, retrying...")
                            retry_count += 1

                    except Exception as e:
                        logger.error(f"Error generating spread {i}: {e}")
                        retry_count += 1
                        if retry_count < self.max_retries:
                            time.sleep(5)

                if retry_count >= self.max_retries:
                    logger.error(f"Spread {i} failed after {self.max_retries} retries")
                    results["failed_images"].append(spread_name)

            # Step 4: Generate back cover
            back_cover_path = output_dir / "back_cover.png"
            if back_cover_path.exists():
                logger.info(f"Using existing back cover: {back_cover_path}")
                results["back_cover"] = back_cover_path
            else:
                logger.info("Step 4/4: Generating back cover...")
                try:
                    _, back_cover_path = self.generate_illustration(
                        story_package["back_cover_scene"],
                        char_sheet_path,
                        illustration_type="back_cover",
                        output_path=back_cover_path,
                        style=art_style
                    )

                    # Skip QA on back cover when qa_first_only is enabled (saves cost)
                    if self.qa_first_only:
                        results["back_cover"] = back_cover_path
                        logger.info("Back cover generated (QA skipped - qa_first_only mode)")
                    else:
                        passed, qa_result = self.qa_check(
                            back_cover_path,
                            story_package["back_cover_scene"]
                        )
                        results["qa_results"]["back_cover"] = {
                            "passed": passed,
                            "result": qa_result
                        }

                        if not passed:
                            results["failed_images"].append("back_cover")
                        else:
                            results["back_cover"] = back_cover_path
                            logger.info("Back cover passed QA")

                except Exception as e:
                    logger.error(f"Failed to generate back cover: {e}")
                    results["failed_images"].append("back_cover")

            # Final summary
            results["success"] = len(results["failed_images"]) == 0

            logger.info("=" * 60)
            logger.info(f"Book Generation Complete")
            logger.info(f"Total spreads generated: {len(results['spreads'])}/12")
            logger.info(f"Failed images: {len(results['failed_images'])}")
            if results["failed_images"]:
                logger.info(f"Failed: {results['failed_images']}")
            logger.info(f"Output directory: {output_dir}")
            logger.info("=" * 60)

            return results

        except Exception as e:
            logger.error(f"Fatal error in pipeline: {e}")
            results["success"] = False
            return results


def main():
    """
    Standalone test/demo of the ArtPipeline.
    """
    # Check for API key
    if not os.environ.get('OPENAI_API_KEY'):
        print("Error: OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    # Initialize pipeline
    pipeline = ArtPipeline()

    # Example story package
    story_package = {
        "character_name": "Luna",
        "character_description": (
            "Luna is a curious young rabbit with long ears, bright dark brown eyes, "
            "soft gray and white fur, and a pink nose. She has an innocent, adventurous expression."
        ),
        "title": "Luna's Adventure",
        "cover_scene": (
            "Luna the rabbit standing on a sunny meadow with wildflowers, looking excited "
            "and ready for adventure. Mountains and blue sky in background."
        ),
        "spreads": [
            "Luna discovers a mysterious blue butterfly near the garden.",
            "Luna chases the butterfly through a field of tall grass.",
            "Luna reaches a beautiful forest with tall trees and dappled sunlight.",
            "Luna meets a wise old owl perched on an ancient oak tree.",
            "The owl shares stories about the magical forest with Luna.",
            "Luna follows a sparkling stream deeper into the forest.",
            "Luna discovers a hidden waterfall surrounded by ferns.",
            "Luna plays in the crystal clear pool at the waterfall's base.",
            "Luna makes friends with playful forest creatures.",
            "The friends explore a mystical cave together.",
            "They discover magical crystals glowing inside the cave.",
            "Luna and friends emerge at sunset, sharing a joyful moment.",
        ],
        "back_cover_scene": (
            "Beautiful landscape with mountains, forest, and sunset sky. "
            "No characters, focus on the magical world of the forest."
        )
    }

    # Generate book
    output_dir = Path.home() / "books_output" / "luna_adventure"
    results = pipeline.generate_all(story_package, output_dir)

    # Print results
    print("\n" + "=" * 60)
    print("GENERATION RESULTS")
    print("=" * 60)
    print(f"Overall Success: {results['success']}")
    print(f"Character Sheet: {results['character_sheet']}")
    print(f"Cover: {results['cover']}")
    print(f"Spreads Generated: {len(results['spreads'])}/12")
    print(f"Back Cover: {results['back_cover']}")
    print(f"Failed Images: {results['failed_images']}")
    print("=" * 60)

    # Save results summary
    summary_path = output_dir / "generation_summary.json"
    summary = {
        "success": results["success"],
        "character_sheet": str(results["character_sheet"]),
        "cover": str(results["cover"]),
        "spreads": [str(p) for p in results["spreads"]],
        "back_cover": str(results["back_cover"]),
        "failed_images": results["failed_images"],
        "output_directory": str(output_dir)
    }

    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nResults saved to: {summary_path}")


if __name__ == "__main__":
    main()
