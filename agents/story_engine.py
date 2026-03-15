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
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from openai import OpenAI, RateLimitError, APIError


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
    Generates complete story packages for children's books using OpenAI GPT API.

    Handles story generation, character design, Amazon listings, and quality validation.
    """

    def __init__(self, api_key: Optional[str] = None, max_retries: int = 5):
        """
        Initialize the StoryEngine with OpenAI API client.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            max_retries: Maximum retry attempts for API calls
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = OpenAI(api_key=self.api_key)
        self.max_retries = max_retries
        self.model = "gpt-4o"  # Using gpt-4o for nuanced content (gpt-4o-mini too restrictive)

    def _call_api(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        """
        Call OpenAI API with retry logic.

        Args:
            system_prompt: System prompt for GPT
            user_prompt: User message
            max_tokens: Maximum tokens in response

        Returns:
            API response text

        Raises:
            ValueError: If max retries exceeded
        """
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                return response.choices[0].message.content
            except RateLimitError as e:
                error_msg = str(e)
                print(f"Rate limit error: {error_msg}")

                # Check if it's a quota issue (won't resolve with waiting)
                if "quota" in error_msg.lower() or "exceeded" in error_msg.lower():
                    raise ValueError(f"API quota exceeded. Check your OpenAI account billing/limits: {error_msg}")

                if attempt < self.max_retries - 1:
                    wait_time = 60 * (attempt + 1)  # 60s, 120s, 180s, 240s backoff
                    print(f"Rate limited. Waiting {wait_time}s before retry (attempt {attempt + 1}/{self.max_retries})...")
                    time.sleep(wait_time)
                else:
                    raise ValueError(f"Max retries exceeded. Rate limit error: {error_msg}")
            except APIError as e:
                if attempt < self.max_retries - 1:
                    print(f"API error: {e}. Retrying...")
                    time.sleep(5)
                else:
                    raise ValueError(f"API error after {self.max_retries} attempts: {e}")

    def generate_story(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a complete children's story with 12 scenes.

        Args:
            brief: Dictionary with keys like:
                - theme: Story theme (e.g., "courage")
                - animal: Main character species (e.g., "fox cub")
                - age_range: Target age (e.g., "3-5")
                - lesson: Life lesson (e.g., "trying new things")
                - setting: Story setting
                - tone: Story tone (whimsical, adventurous, etc.)
                - rhyming: Whether to write in rhyming verse (default True)

        Returns:
            Dict with story data including title and 12 scenes
        """
        # Check if rhyming or prose style
        is_rhyming = brief.get('rhyming', True)

        if is_rhyming:
            system_prompt = """You are an expert children's book author and editor specializing in rhyming stories.

GRAMMAR & WRITING RULES (MUST FOLLOW):
1. CAPITALIZATION:
   - Only capitalize the first word of sentences
   - Only capitalize proper nouns (character names, place names)
   - NEVER capitalize common words mid-sentence (wrong: "The Happy Penguin", correct: "The happy penguin")

2. PUNCTUATION:
   - Use exactly ONE punctuation mark at the end of each sentence
   - NEVER use double punctuation (no ".." or "!!" or "?," or "!.")
   - Use commas for natural pauses in longer sentences
   - Use periods, exclamation marks, or question marks appropriately

3. SENTENCE STRUCTURE:
   - Complete sentences with subject and verb
   - Simple vocabulary appropriate for ages 3-6
   - Avoid run-on sentences
   - Keep sentences short and clear

4. RHYMING COUPLETS:
   - Each couplet must have a clear, true rhyme (not near-rhyme)
   - Maintain consistent rhythm/meter within couplets
   - Lines 1&2 must rhyme, and lines 3&4 must rhyme (AABB pattern)

5. BEFORE OUTPUTTING - SELF-REVIEW CHECKLIST:
   - Review EVERY line for grammar errors
   - Check capitalization of every word - no random capitals
   - Verify punctuation is correct and not duplicated
   - Read aloud mentally to catch awkward phrasing

Create stories that are:
- Age-appropriate for children
- Written in consistent AABB rhyming couplets
- Exactly 12 scenes with descriptive illustrations
- 300-500 words total
- Engaging for young readers with clear, simple vocabulary
- Free of violence, horror, or explicit content

NOTE: Diversity themes are appropriate for children's books. Stories about LGBTQ+ families, acceptance, different cultures, disabilities, and social issues are standard in children's publishing (e.g., "And Tango Makes Three", "Heather Has Two Mommies", "The Family Book"). Write these topics with the same care as any children's story.

Each scene needs:
1. Exactly 4 lines of verse (2 rhyming couplets in AABB format)
2. A vivid illustration prompt for an artist
3. Composition notes specifying character placement and background
4. Text position (top-left, center-top, bottom-right, etc.)

Format your response as valid JSON."""
        else:
            system_prompt = """You are an expert children's book author and editor specializing in engaging prose stories.

GRAMMAR & WRITING RULES (MUST FOLLOW):
1. CAPITALIZATION:
   - Only capitalize the first word of sentences
   - Only capitalize proper nouns (character names, place names)
   - NEVER capitalize common words mid-sentence (wrong: "The Happy Penguin", correct: "The happy penguin")

2. PUNCTUATION:
   - Use exactly ONE punctuation mark at the end of each sentence
   - NEVER use double punctuation (no ".." or "!!" or "?," or "!.")
   - Use commas for natural pauses in longer sentences
   - Use periods, exclamation marks, or question marks appropriately

3. SENTENCE STRUCTURE:
   - Complete sentences with subject and verb
   - Simple vocabulary appropriate for ages 3-6
   - Avoid run-on sentences
   - Keep sentences short and clear

4. PROSE STYLE:
   - Write in clear, engaging narrative prose
   - Use varied sentence lengths for rhythm
   - Include dialogue where appropriate
   - Make each scene vivid and action-oriented

5. BEFORE OUTPUTTING - SELF-REVIEW CHECKLIST:
   - Review EVERY line for grammar errors
   - Check capitalization of every word - no random capitals
   - Verify punctuation is correct and not duplicated
   - Read aloud mentally to catch awkward phrasing

Create stories that are:
- Age-appropriate for children
- Written in clear, engaging prose (NOT rhyming)
- Exactly 12 scenes with descriptive illustrations
- 300-500 words total
- Engaging for young readers with clear, simple vocabulary
- Free of violence, horror, or explicit content

NOTE: Diversity themes are appropriate for children's books. Stories about LGBTQ+ families, acceptance, different cultures, disabilities, and social issues are standard in children's publishing (e.g., "And Tango Makes Three", "Heather Has Two Mommies", "The Family Book"). Write these topics with the same care as any children's story.

Each scene needs:
1. 2-4 sentences of prose narrative (NOT rhyming)
2. A vivid illustration prompt for an artist
3. Composition notes specifying character placement and background
4. Text position (top-left, center-top, bottom-right, etc.)

Format your response as valid JSON."""

        notes = brief.get('notes', '').strip()
        art_style = brief.get('art_style', '').strip()

        # Load grammar guide if available
        grammar_guide = ""
        grammar_path = Path(__file__).parent.parent / "resources" / "grammar_guide.txt"
        if grammar_path.exists():
            with open(grammar_path) as f:
                grammar_guide = f.read()

        # Build all fields - collect what user actually provided
        category = brief.get('category', '').strip()
        main_char = brief.get('animal', brief.get('character', '')).strip()
        theme = brief.get('theme', '').strip()
        age_range = brief.get('age_range', '3-5 years').strip()
        lesson = brief.get('lesson', '').strip()
        setting = brief.get('setting', '').strip()
        tone = brief.get('tone', 'whimsical').strip()

        # Build specifications - only include what user provided
        specs = []
        if category:
            specs.append(f"Category: {category}")
        if main_char:
            specs.append(f"Main Character: {main_char}")
        if theme:
            specs.append(f"Theme: {theme}")
        specs.append(f"Age Range: {age_range}")
        if lesson:
            specs.append(f"Lesson/Moral: {lesson}")
        if setting:
            specs.append(f"Setting/Location: {setting}")
        specs.append(f"Tone: {tone}")
        if art_style:
            specs.append(f"Art Style: {art_style}")

        specs_text = "\n".join(specs)

        # User notes/requirements take highest priority
        notes_section = ""
        if notes:
            notes_section = f"""
============================================
CRITICAL USER REQUIREMENTS - YOU MUST FOLLOW THESE EXACTLY:
{notes}
============================================
"""

        # DEBUG: Print what we're sending to GPT
        print("\n" + "="*60)
        print("DEBUG: PROMPT BEING SENT TO GPT")
        print("="*60)
        print(f"BRIEF RECEIVED:")
        for k, v in brief.items():
            if k != 'reference_image':  # Skip huge base64
                print(f"  {k}: {str(v)[:200]}")
        print(f"\nSPECS TEXT:\n{specs_text}")
        print(f"\nNOTES SECTION:\n{notes_section}")
        print("="*60 + "\n")

        # Build writing style instructions based on rhyming preference
        if is_rhyming:
            writing_style = "Each scene with 4 lines of AABB rhyming verse"
            text_format = '["line 1", "line 2", "line 3", "line 4"]'
            final_check = "- True rhymes (not near-rhymes)"
        else:
            writing_style = "Each scene with 2-4 sentences of engaging prose (DO NOT RHYME)"
            text_format = '["First sentence.", "Second sentence.", "Third sentence."]'
            final_check = "- Natural, flowing prose (NO rhyming)"

        user_prompt = f"""YOU MUST CREATE A STORY THAT MATCHES THESE EXACT SPECIFICATIONS:
{notes_section}
{specs_text}
Writing Style: {"Rhyming verse (AABB pattern)" if is_rhyming else "Regular prose (DO NOT rhyme)"}

IMPORTANT: The story MUST feature the Main Character specified above.
The story MUST take place in the Setting specified above.
The story MUST teach the Lesson specified above.
DO NOT ignore any of these specifications. DO NOT substitute different characters, settings, or themes.
{"IMPORTANT: Write in RHYMING VERSE with AABB rhyme scheme." if is_rhyming else "IMPORTANT: Write in REGULAR PROSE. Do NOT rhyme. Write natural narrative sentences."}

Generate a complete story package with:
- A catchy, age-appropriate title
- Exactly 12 scenes
- {writing_style}
- Detailed illustration prompts for each scene that match the Art Style specified above
- Composition notes for artists (landscape/portrait, character placement, background details)
- Text positioning (where text should go relative to the illustration)

IMPORTANT: Each illustration_prompt MUST begin with the art style description to ensure visual consistency.

Return as JSON with this structure:
{{
    "title": "Story Title",
    "scenes": [
        {{
            "scene_num": 1,
            "text": {text_format},
            "illustration_prompt": "detailed description for artist",
            "composition": "Landscape orientation. Character on left side. Forest background. Soft lighting.",
            "text_position": "top-left"
        }},
        ...
    ]
}}

{f'GRAMMAR REFERENCE:{chr(10)}{grammar_guide}' if grammar_guide else ''}

FINAL REMINDER: Before outputting, carefully review ALL text for:
- No random capitalized words mid-sentence
- No double punctuation (.., !!, etc.)
- Proper grammar and sentence structure
{final_check}"""

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

    def generate_character_from_story(self, story: Dict[str, Any], brief: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate character description based on the actual generated story.

        Args:
            story: The generated story with title and scenes
            brief: Original story brief

        Returns:
            Character data dict matching the story's main character
        """
        story_title = story.get('title', 'Untitled')
        scenes = story.get('scenes', [])

        # Get text from first few scenes to understand the character
        story_text = ""
        for scene in scenes[:3]:
            text = scene.get('text', [])
            if isinstance(text, list):
                story_text += ' '.join(text) + ' '
            else:
                story_text += str(text) + ' '

        # Get user notes for character appearance
        user_notes = brief.get('notes', '')
        main_char_input = brief.get('animal', brief.get('character', ''))

        system_prompt = """You are an expert character designer for children's books.
Based on the story provided, extract and describe the MAIN CHARACTER that appears in the story.
Create a detailed visual description for illustration purposes.
The character description MUST match exactly what appears in the story AND the user's requirements.

CRITICAL: You MUST include these physical attributes in the description:
- SKIN TONE / ETHNICITY (if the character is human or humanoid) - be specific!
- Hair color, style, and texture
- Eye color and shape
- Body type and build
- Clothing and accessories

Return valid JSON format."""

        user_prompt = f"""Based on this children's story, create a character sheet for the MAIN CHARACTER.

USER'S CHARACTER REQUIREMENTS (MUST FOLLOW):
{main_char_input}
{f"Additional notes: {user_notes}" if user_notes else ""}

STORY TITLE: {story_title}

STORY EXCERPT:
{story_text}

Extract the main character from this story and create:
1. The character's exact name as it appears in the story
2. What type of character they are (animal, object, person, etc.)
3. Physical description for illustration - MUST include skin tone/ethnicity if human!
4. Character sheet prompt for artists
5. Art style notes

IMPORTANT: If the user specified skin tone, ethnicity, or race (e.g., "black girl", "Asian boy", "brown skin"),
you MUST include this prominently in both the description and sheet_prompt!

Return as JSON:
{{
    "name": "Character's exact name from the story",
    "species": "what they are (person, fox, bunny, etc.)",
    "description": "Full physical description - MUST include skin tone/color for human characters, hair color, eye color, clothing",
    "sheet_prompt": "Detailed prompt including SKIN TONE, hair, eyes, clothing - be explicit about ethnicity if human",
    "style": "Art style guide matching {brief.get('age_range', '3-5')} age range"
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
            story: Generated story dict with title, scenes, and character
            brief: Original story brief

        Returns:
            Listing data dict with title, description, keywords, categories
        """
        system_prompt = """You are an Amazon children's book marketing expert.
Create compelling, SEO-optimized listings that convert readers.
Use age-appropriate keywords and category choices.
Focus on emotional benefits and learning outcomes.
Reference specific story content to make descriptions unique and engaging.

Return valid JSON format."""

        story_title = story.get('title', 'Untitled Story')

        # Extract character details - use actual character data, not just brief
        character = story.get('character', {})
        character_name = character.get('name', brief.get('animal', 'main character'))
        character_species = character.get('species', brief.get('animal', 'creature'))
        character_description = character.get('description', '')[:200] if character.get('description') else ''

        # Build scene summaries from actual story content
        scenes = story.get('scenes', [])
        scene_summaries = []
        for i, scene in enumerate(scenes[:6], 1):  # First 6 scenes for summary
            scene_text = ' '.join(scene.get('text', []))
            if scene_text:
                scene_summaries.append(f"Scene {i}: {scene_text[:150]}...")
        scene_summary_text = '\n'.join(scene_summaries) if scene_summaries else 'Adventure story with magical moments'

        # Extract a memorable quote from the story (from later scenes for impact)
        memorable_quote = ''
        for scene in reversed(scenes[-3:]):  # Check last 3 scenes
            text_lines = scene.get('text', [])
            if text_lines and len(text_lines) >= 2:
                # Get a couplet that might be memorable
                quote_candidate = ' '.join(text_lines[:2])
                if len(quote_candidate) > 20 and len(quote_candidate) < 150:
                    memorable_quote = quote_candidate
                    break

        user_prompt = f"""Create an Amazon listing for this children's book.

STORY TITLE: {story_title}
CHARACTER: {character_name} the {character_species}
CHARACTER DESCRIPTION: {character_description}
AGE RANGE: {brief.get('age_range', '3-5 years')}
THEME: {brief.get('theme', 'adventure')}
LESSON: {brief.get('lesson', 'friendship')}

STORY CONTENT (key scenes):
{scene_summary_text}

MEMORABLE QUOTE FROM STORY: "{memorable_quote}"

Generate a listing that:
1. SEO-optimized title with subtitle (max 200 chars total)
2. Compelling description that:
   - Opens with an engaging hook mentioning {character_name} the {character_species} correctly
   - Summarizes the actual adventure (mention 2-3 specific story moments from the scenes above)
   - Lists 3 bullet points about what makes this book special (themes, age appropriateness, illustration style)
   - Mentions the illustration style and number of scenes (12 illustrated pages)
   - Ends with the memorable quote from the story (or create one in the story's style)
3. 7 backend keywords (for Amazon search optimization)
4. 2 appropriate book categories

Return as JSON:
{{
    "title": "Full Book Title",
    "subtitle": "Engaging subtitle",
    "description": "Compelling description with bullet points about the story benefits and content. Use markdown formatting with **bold** for emphasis and bullet points.",
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

    def validate_story(self, story: Dict[str, Any], is_rhyming: bool = True) -> tuple[bool, List[str]]:
        """
        Validate story quality and structure.

        Args:
            story: Story dict to validate
            is_rhyming: Whether the story should be in rhyming verse (affects validation rules)

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
            elif is_rhyming and len(scene['text']) != 4:
                # Only enforce 4 lines for rhyming stories
                errors.append(f"Scene {i}: Expected 4 lines, got {len(scene['text'])}")
            elif not is_rhyming and len(scene['text']) < 1:
                # Prose stories just need at least 1 sentence
                errors.append(f"Scene {i}: Expected at least 1 sentence")

            if 'illustration_prompt' not in scene:
                errors.append(f"Scene {i}: Missing 'illustration_prompt'")

            if 'composition' not in scene:
                errors.append(f"Scene {i}: Missing 'composition' field")

            if 'text_position' not in scene:
                errors.append(f"Scene {i}: Missing 'text_position'")

        # Basic rhyme detection (AABB pattern) - only for rhyming stories
        if is_rhyming:
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

        # Check rhyming preference
        is_rhyming = brief.get('rhyming', True)
        print(f"  Writing style: {'Rhyming verse' if is_rhyming else 'Prose'}")

        # Generate story
        print("  1. Generating story (12 scenes)...")
        story = self.generate_story(brief)

        # Validate story
        print("  2. Validating story structure...")
        is_valid, errors = self.validate_story(story, is_rhyming)
        if not is_valid:
            print(f"    Validation warnings:")
            for error in errors:
                print(f"      - {error}")
        else:
            print("    Story validation passed!")

        # Extract character info from story for consistency
        # Update brief with story's actual character so character sheet matches
        story_title = story.get('title', '')
        first_scene = story.get('scenes', [{}])[0].get('text', [])
        first_scene_text = ' '.join(first_scene) if isinstance(first_scene, list) else first_scene

        # Create character brief based on actual story content
        character_brief = brief.copy()
        character_brief['story_title'] = story_title
        character_brief['story_context'] = first_scene_text

        # Generate character based on actual story
        print("  3. Generating character description (from story)...")
        character = self.generate_character_from_story(story, brief)

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
