"""
Story Generation Engine for Automated Children's Book Publishing Studio

This module generates complete story packages including:
- Rhyming children's stories (300-500 words, 12 scenes)
- Detailed character descriptions with illustration prompts
- SEO-optimized Amazon listings
- Quality validation and error handling
"""

import json
import os
import re
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import anthropic


@dataclass
class SceneData:
    """Represents a single scene in the story."""
    scene_num: int
    text: List[str]  # 4 lines of verse
    illustration_prompt: str
    composition: str
    text_position: str


@dataclass
class CharacterData:
    """Represents the main character."""
    name: str
    species: str
    description: str
    sheet_prompt: str
    style: str


@dataclass
class ListingData:
    """Represents the Amazon listing."""
    title: str
    subtitle: str
    description: str
    keywords: List[str]
    categories: List[str]


class StoryEngine:
    """
    Generates complete story packages for children's books using Claude API.

    Handles story generation, character design, Amazon listings, and quality validation.
    """

    def __init__(self, api_key: Optional[str] = None, max_retries: int = 3):
        """
        Initialize the StoryEngine with Anthropic API client.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            max_retries: Maximum retry attempts for API calls
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.max_retries = max_retries
        self.model = "claude-3-5-sonnet-20241022"

    def _call_api(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        """
        Call Claude API with retry logic.

        Args:
            system_prompt: System prompt for Claude
            user_prompt: User message
            max_tokens: Maximum tokens in response

        Returns:
            API response text

        Raises:
            ValueError: If max retries exceeded
        """
        for attempt in range(self.max_retries):
            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )
                return message.content[0].text
            except anthropic.RateLimitError:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    raise ValueError("Max retries exceeded due to rate limiting")
            except anthropic.APIError as e:
                if attempt < self.max_retries - 1:
                    print(f"API error: {e}. Retrying...")
                    time.sleep(1)
                else:
                    raise ValueError(f"API error after {self.max_retries} attempts: {e}")

    def generate_story(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a complete rhyming children's story with 12 scenes.

        Args:
            brief: Dictionary with keys like:
                - theme: Story theme (e.g., "courage")
                - animal: Main character species (e.g., "fox cub")
                - age_range: Target age (e.g., "3-5")
                - lesson: Life lesson (e.g., "trying new things")
                - setting: Story setting
                - tone: Story tone (whimsical, adventurous, etc.)

        Returns:
            Dict with story data including title and 12 scenes
        """
        system_prompt = """You are an expert children's book author specializing in rhyming stories.
Create stories that are:
- Age-appropriate and wholesome
- Written in consistent AABB rhyming couplets
- Exactly 12 scenes with descriptive illustrations
- 300-500 words total
- Engaging for young readers with clear, simple vocabulary
- Free of scary or inappropriate content

Each scene needs:
1. Exactly 4 lines of verse (2 rhyming couplets in AABB format)
2. A vivid illustration prompt for an artist
3. Composition notes specifying character placement and background
4. Text position (top-left, center-top, bottom-right, etc.)

Format your response as valid JSON."""

        user_prompt = f"""Create a children's story with these specifications:
Theme: {brief.get('theme', 'adventure')}
Main Character: {brief.get('animal', 'woodland creature')}
Age Range: {brief.get('age_range', '3-5 years')}
Lesson: {brief.get('lesson', 'friendship')}
Setting: {brief.get('setting', 'enchanted forest')}
Tone: {brief.get('tone', 'whimsical')}

Generate a complete story package with:
- A catchy, age-appropriate title
- Exactly 12 scenes
- Each scene with 4 lines of AABB rhyming verse
- Detailed illustration prompts for each scene
- Composition notes for artists (landscape/portrait, character placement, background details)
- Text positioning (where text should go relative to the illustration)

Return as JSON with this structure:
{{
    "title": "Story Title",
    "scenes": [
        {{
            "scene_num": 1,
            "text": ["line 1", "line 2", "line 3", "line 4"],
            "illustration_prompt": "detailed description for artist",
            "composition": "Landscape orientation. Character on left side. Forest background. Soft lighting.",
            "text_position": "top-left"
        }},
        ...
    ]
}}"""

        response = self._call_api(system_prompt, user_prompt, max_tokens=4096)

        # Extract JSON from response
        try:
            story_data = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
            if json_match:
                story_data = json.loads(json_match.group(1))
            else:
                raise ValueError(f"Failed to parse story JSON response: {response[:200]}")

        return story_data

    def generate_character(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate detailed character description with illustration prompt.

        Args:
            brief: Dictionary with theme, animal, and other story details

        Returns:
            Character data dict with appearance, sheet prompt, and style
        """
        system_prompt = """You are an expert character designer for children's books.
Create vivid, memorable character descriptions that are perfect for illustration.
Include specific details about appearance, personality, and visual style.
Always include detailed eye descriptions - eyes are crucial for emotion and connection.

Return valid JSON format."""

        user_prompt = f"""Design a character for a children's book with these specs:
Animal/Species: {brief.get('animal', 'woodland creature')}
Theme: {brief.get('theme', 'adventure')}
Age Range: {brief.get('age_range', '3-5 years')}
Lesson: {brief.get('lesson', 'friendship')}

Create a detailed character with:
1. A charming name
2. Physical description (fur/feather color, size, distinctive features)
3. Eyes (this is critical - describe color, shape, expression, and how eyes convey emotion)
4. Proportions (age-appropriate, cute/appealing for target age)
5. A character sheet prompt for illustration
6. Visual style notes (style guide for artists)

Return as JSON:
{{
    "name": "Character Name",
    "species": "animal species",
    "description": "Full physical description including fur color, eye color and detail, size, distinctive marks, and personality traits visible in appearance",
    "sheet_prompt": "Detailed prompt for generating character sheet illustration",
    "style": "Art style guide (e.g., 'Soft, rounded shapes. Gentle colors. Expressive eyes. Whimsical and warm.')"
}}"""

        response = self._call_api(system_prompt, user_prompt, max_tokens=2048)

        try:
            character_data = json.loads(response)
        except json.JSONDecodeError:
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
            if json_match:
                character_data = json.loads(json_match.group(1))
            else:
                raise ValueError(f"Failed to parse character JSON: {response[:200]}")

        return character_data

    def generate_listing(self, story: Dict[str, Any], brief: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate SEO-optimized Amazon listing.

        Args:
            story: Generated story dict with title
            brief: Original story brief

        Returns:
            Listing data dict with title, description, keywords, categories
        """
        system_prompt = """You are an Amazon children's book marketing expert.
Create compelling, SEO-optimized listings that convert readers.
Use age-appropriate keywords and category choices.
Focus on emotional benefits and learning outcomes.

Return valid JSON format."""

        story_title = story.get('title', 'Untitled Story')
        user_prompt = f"""Create an Amazon listing for this children's book:
Story Title: {story_title}
Theme: {brief.get('theme', 'adventure')}
Main Character: {brief.get('animal', 'woodland creature')}
Age Range: {brief.get('age_range', '3-5 years')}
Lesson: {brief.get('lesson', 'friendship')}

Generate:
1. SEO-optimized title with subtitle (max 200 chars total)
2. Compelling description with bullet points highlighting:
   - Age appropriateness
   - Learning outcome
   - Story appeal
   - Illustration quality
3. 7 backend keywords (for Amazon search optimization)
4. 2 appropriate book categories

Return as JSON:
{{
    "title": "Full Book Title",
    "subtitle": "Engaging subtitle",
    "description": "Compelling description with bullet points about the story benefits and content",
    "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6", "keyword7"],
    "categories": ["Children's Books > Animals", "Children's Books > Emotions & Feelings"]
}}"""

        response = self._call_api(system_prompt, user_prompt, max_tokens=2048)

        try:
            listing_data = json.loads(response)
        except json.JSONDecodeError:
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
            if json_match:
                listing_data = json.loads(json_match.group(1))
            else:
                raise ValueError(f"Failed to parse listing JSON: {response[:200]}")

        return listing_data

    def validate_story(self, story: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate story quality and structure.

        Args:
            story: Story dict to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check scene count
        scenes = story.get('scenes', [])
        if len(scenes) != 12:
            errors.append(f"Expected 12 scenes, got {len(scenes)}")

        # Check word count
        all_text = ' '.join(
            ' '.join(scene.get('text', []))
            for scene in scenes
        )
        word_count = len(all_text.split())
        if word_count < 300:
            errors.append(f"Story too short: {word_count} words (minimum 300)")
        elif word_count > 500:
            errors.append(f"Story too long: {word_count} words (maximum 500)")

        # Check scene structure
        for i, scene in enumerate(scenes, 1):
            if 'text' not in scene or not isinstance(scene['text'], list):
                errors.append(f"Scene {i}: Missing or invalid 'text' field")
            elif len(scene['text']) != 4:
                errors.append(f"Scene {i}: Expected 4 lines, got {len(scene['text'])}")

            if 'illustration_prompt' not in scene:
                errors.append(f"Scene {i}: Missing 'illustration_prompt'")

            if 'composition' not in scene:
                errors.append(f"Scene {i}: Missing 'composition' field")

            if 'text_position' not in scene:
                errors.append(f"Scene {i}: Missing 'text_position'")

        # Basic rhyme detection (AABB pattern)
        rhyme_issues = 0
        for i, scene in enumerate(scenes, 1):
            text = scene.get('text', [])
            if len(text) >= 2:
                # Check if lines likely rhyme (simplified check based on ending sounds)
                for j in range(0, min(4, len(text)), 2):
                    if j + 1 < len(text):
                        line1_end = text[j].split()[-1].lower() if text[j].split() else ""
                        line2_end = text[j + 1].split()[-1].lower() if text[j + 1].split() else ""
                        # Simple check: last 2-3 characters should be similar
                        if line1_end and line2_end:
                            if line1_end[-2:] != line2_end[-2:]:
                                rhyme_issues += 1

        if rhyme_issues > 0:
            errors.append(f"Potential rhyme issues detected in {rhyme_issues} couplet(s)")

        # Check for problematic content (very basic)
        problematic_words = ['scary', 'evil', 'dark', 'death', 'blood', 'violence']
        for scene in scenes:
            text_content = ' '.join(scene.get('text', [])).lower()
            for word in problematic_words:
                if word in text_content:
                    errors.append(f"Potentially problematic content detected: '{word}'")
                    break

        return len(errors) == 0, errors

    def run(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute full pipeline: generate story, character, and listing.

        Args:
            brief: Story brief with theme, animal, age_range, lesson, setting, tone

        Returns:
            Complete story package as JSON-serializable dict
        """
        print(f"Starting story generation pipeline for: {brief.get('theme', 'untitled')}")

        # Generate story
        print("  1. Generating story (12 scenes)...")
        story = self.generate_story(brief)

        # Validate story
        print("  2. Validating story structure...")
        is_valid, errors = self.validate_story(story)
        if not is_valid:
            print(f"    Validation warnings:")
            for error in errors:
                print(f"      - {error}")
        else:
            print("    Story validation passed!")

        # Generate character
        print("  3. Generating character description...")
        character = self.generate_character(brief)

        # Generate listing
        print("  4. Generating Amazon listing...")
        listing = self.generate_listing(story, brief)

        # Build complete package
        package = {
            "story": story,
            "character": character,
            "listing": listing,
            "metadata": {
                "brief": brief,
                "validation": {
                    "is_valid": is_valid,
                    "errors": errors
                }
            }
        }

        print("  Pipeline complete!")
        return package


def main():
    """
    Standalone example: Generate a complete children's book story package.
    """
    # Example story brief
    sample_brief = {
        "theme": "courage",
        "animal": "fox cub",
        "age_range": "3-5 years",
        "lesson": "facing your fears",
        "setting": "enchanted forest by moonlight",
        "tone": "gentle and whimsical"
    }

    print("=" * 60)
    print("Children's Book Story Engine - Sample Generation")
    print("=" * 60)
    print()

    try:
        # Initialize engine
        engine = StoryEngine()

        # Generate complete package
        print(f"Brief: {sample_brief}")
        print()

        package = engine.run(sample_brief)

        # Display results
        print()
        print("=" * 60)
        print("GENERATED STORY PACKAGE")
        print("=" * 60)
        print()

        print("STORY TITLE:", package['story']['title'])
        print(f"SCENES: {len(package['story']['scenes'])}")
        print()

        print("First Scene Preview:")
        scene1 = package['story']['scenes'][0]
        print(f"  Scene {scene1['scene_num']}:")
        for line in scene1['text']:
            print(f"    {line}")
        print(f"  Illustration: {scene1['illustration_prompt'][:80]}...")
        print(f"  Position: {scene1['text_position']}")
        print()

        print("CHARACTER:")
        print(f"  Name: {package['character']['name']}")
        print(f"  Species: {package['character']['species']}")
        print(f"  Description: {package['character']['description'][:100]}...")
        print()

        print("AMAZON LISTING:")
        print(f"  Title: {package['listing']['title']}")
        print(f"  Keywords: {', '.join(package['listing']['keywords'][:3])}...")
        print(f"  Categories: {', '.join(package['listing']['categories'])}")
        print()

        print("VALIDATION:")
        validation = package['metadata']['validation']
        print(f"  Valid: {validation['is_valid']}")
        if validation['errors']:
            print(f"  Issues:")
            for error in validation['errors']:
                print(f"    - {error}")
        print()

        # Save full output
        output_file = "/tmp/story_package.json"
        with open(output_file, 'w') as f:
            json.dump(package, f, indent=2)
        print(f"Full package saved to: {output_file}")
        print()

        return package

    except ValueError as e:
        print(f"Error: {e}")
        return None


if __name__ == "__main__":
    main()
