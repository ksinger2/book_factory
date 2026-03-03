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


class ArtPipeline:
    """
    Manages the complete art generation pipeline for children's book illustrations.

    Uses OpenAI's image generation and editing APIs to create character-consistent
    illustrations with vision-based quality assurance.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4-turbo"):
        """
        Initialize the ArtPipeline.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY environment variable.
            model: Vision model to use for QA checks. Defaults to gpt-4-turbo.

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
        self.image_model = "gpt-4o"  # Image generation model

        # QA thresholds
        self.max_retries = 3
        self.initial_backoff = 30  # seconds

        logger.info(f"ArtPipeline initialized with model: {model}")

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

    def _add_eye_safety_instructions(self, prompt: str) -> str:
        """
        Add critical eye consistency instructions to prompt.

        Args:
            prompt: Original prompt text

        Returns:
            Prompt with eye safety instructions prepended
        """
        eye_instructions = (
            "CRITICAL — CHARACTER EYES: Large, round, dark brown irises. "
            "Each eye MUST have TWO small bright white highlight dots. "
            "Do NOT make eyes solid black.\n\n"
        )
        return eye_instructions + prompt

    def generate_character_sheet(
        self,
        character_desc: str,
        output_path: Optional[Path] = None
    ) -> Tuple[str, Path]:
        """
        Generate a character reference sheet with multiple poses and expressions.

        Uses images.generate() to create a comprehensive character sheet showing
        the character in various poses and emotional expressions.

        Args:
            character_desc: Description of the character to generate
            output_path: Where to save the character sheet. If None, uses default location.

        Returns:
            Tuple of (image_data as base64, saved_path)

        Raises:
            Exception: If generation fails after retries
        """
        if output_path is None:
            output_path = Path.home() / "books_output" / "character_sheets" / "character.png"

        prompt = (
            f"{character_desc}\n\n"
            "Create a character reference sheet showing:\n"
            "1. Full body frontal view (neutral expression)\n"
            "2. Side profile view\n"
            "3. Close-up face showing happy expression\n"
            "4. Close-up face showing sad expression\n"
            "5. Back view\n\n"
            "Ensure consistent proportions and style across all poses. "
            "Include clothing and distinctive features consistently. "
            "Use a clean white background with subtle shadows."
        )

        logger.info(f"Generating character sheet: {character_desc[:50]}...")

        attempt = 0
        while attempt <= self.max_retries:
            try:
                response = self.client.images.generate(
                    model=self.image_model,
                    prompt=prompt,
                    size="1536x1024",
                    quality="hd",
                    n=1,
                    response_format="b64_json"
                )

                image_data = response.data[0].b64_json
                self._save_image(image_data, output_path)
                logger.info("Character sheet generated successfully")
                return image_data, output_path

            except RateLimitError:
                if attempt < self.max_retries:
                    self._exponential_backoff(attempt)
                    attempt += 1
                else:
                    raise Exception("Character sheet generation failed after max retries")
            except Exception as e:
                logger.error(f"Error generating character sheet: {e}")
                if attempt < self.max_retries:
                    attempt += 1
                    time.sleep(5)
                else:
                    raise

        raise Exception("Character sheet generation failed")

    def generate_illustration(
        self,
        scene_description: str,
        char_sheet_path: Path,
        illustration_type: str = "spread",
        output_path: Optional[Path] = None
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

        Returns:
            Tuple of (image_data as base64, saved_path)

        Raises:
            FileNotFoundError: If character sheet path doesn't exist
            Exception: If generation fails after retries
        """
        if not char_sheet_path.exists():
            raise FileNotFoundError(f"Character sheet not found: {char_sheet_path}")

        if output_path is None:
            output_path = Path.home() / "books_output" / "spreads" / f"spread_{int(time.time())}.png"

        # Determine size based on type
        if illustration_type == "cover":
            size = "1024x1536"  # Portrait for cover
        elif illustration_type == "back_cover":
            size = "1024x1536"
        else:
            size = "1536x1024"  # Landscape for spreads

        # Build prompt with eye safety instructions
        if illustration_type == "back_cover":
            base_prompt = (
                f"{scene_description}\n\n"
                "This is the back cover. Show a beautiful landscape or scene setting "
                "WITHOUT any characters. Focus on the environment, mood, and design elements."
            )
        else:
            base_prompt = (
                f"{scene_description}\n\n"
                "Integrate the character from the reference sheet into this scene. "
                "Maintain consistent character design, proportions, and style. "
                "Ensure the character's pose and expression match the emotional tone of the scene."
            )

        prompt = self._add_eye_safety_instructions(base_prompt)

        logger.info(f"Generating {illustration_type}: {scene_description[:50]}...")

        attempt = 0
        while attempt <= self.max_retries:
            try:
                with open(char_sheet_path, 'rb') as f:
                    response = self.client.images.edit(
                        model=self.image_model,
                        image=f,
                        prompt=prompt,
                        size=size,
                        quality="hd",
                        n=1,
                        response_format="b64_json"
                    )

                image_data = response.data[0].b64_json
                self._save_image(image_data, output_path)
                logger.info(f"{illustration_type.capitalize()} generated successfully")
                return image_data, output_path

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
            response = self.client.messages.create(
                model=self.vision_model,
                max_tokens=500,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_data
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

            qa_result = response.content[0].text
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
        output_dir: Optional[Path] = None
    ) -> Tuple[bool, str]:
        """
        Regenerate a single image that failed QA.

        Args:
            image_name: Name of the image to regenerate
            char_sheet_path: Path to character sheet
            scene_description: Scene description for regeneration
            illustration_type: Type of illustration
            output_dir: Directory to save output

        Returns:
            Tuple of (success boolean, path_or_error_message)
        """
        if output_dir is None:
            output_dir = Path.home() / "books_output"

        output_path = output_dir / "spreads" / image_name

        logger.info(f"Regenerating image: {image_name}")

        try:
            _, saved_path = self.generate_illustration(
                scene_description,
                char_sheet_path,
                illustration_type,
                output_path
            )

            passed, qa_result = self.qa_check(saved_path, scene_description)
            if passed:
                logger.info(f"Image regenerated successfully: {image_name}")
                return True, str(saved_path)
            else:
                logger.warning(f"Regenerated image still failing QA: {image_name}")
                return False, "Image regenerated but still failed QA"

        except Exception as e:
            logger.error(f"Error fixing image {image_name}: {e}")
            return False, str(e)

    def generate_all(
        self,
        story_package: Dict,
        output_dir: Optional[Path] = None
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
            output_dir: Directory to save all output files

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
            else:
                logger.info("Step 1/3: Generating character sheet...")
                try:
                    _, char_sheet_path = self.generate_character_sheet(
                        story_package["character_description"],
                        char_sheet_path
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
                        output_path=cover_path
                    )

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
                while retry_count <= self.max_retries:
                    try:
                        _, spread_path = self.generate_illustration(
                            spread_description,
                            char_sheet_path,
                            illustration_type="spread",
                            output_path=spread_path
                        )

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
                        if retry_count <= self.max_retries:
                            time.sleep(5)

                if retry_count > self.max_retries:
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
                        output_path=back_cover_path
                    )

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
