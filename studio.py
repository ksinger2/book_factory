#!/usr/bin/env python3
"""
Book Factory Studio - Automated Children's Book Publishing Orchestrator

Main entry point that ties all modules together for the full publishing pipeline:
research -> story generation -> art creation -> PDF production -> KDP publishing
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
import uuid
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^80}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.END}\n")


def print_step(step_num: int, total: int, text: str):
    """Print a step in the pipeline"""
    print(f"{Colors.BLUE}[STEP {step_num}/{total}]{Colors.END} {Colors.BOLD}{text}{Colors.END}")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓{Colors.END} {text}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠{Colors.END} {text}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗{Colors.END} {text}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ{Colors.END} {text}")


class ConfigLoader:
    """Load and manage configuration"""

    def __init__(self, config_path: str = None):
        """Initialize config loader"""
        if config_path is None:
            # Look for config relative to this script
            script_dir = Path(__file__).parent
            config_path = script_dir / "config" / "studio_config.yaml"

        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            print_error(f"Config file not found: {self.config_path}")
            sys.exit(1)

        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            print_success(f"Loaded config from {self.config_path}")
            return config
        except Exception as e:
            print_error(f"Failed to load config: {e}")
            sys.exit(1)

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot notation key"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default


class BookID:
    """Generate and manage book IDs"""

    @staticmethod
    def generate(niche: str = None) -> str:
        """Generate a unique book ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique = str(uuid.uuid4())[:8]

        if niche:
            # Clean niche name for ID
            clean_niche = niche.lower().replace(" ", "-").replace("'", "")[:20]
            return f"book-{timestamp}-{clean_niche}-{unique}"
        else:
            return f"book-{timestamp}-{unique}"


class PipelineState:
    """Manage pipeline state and resume capability"""

    def __init__(self, output_dir: Path):
        """Initialize pipeline state"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.output_dir / ".pipeline_state.json"
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load existing state or create new"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")
                return self._new_state()
        return self._new_state()

    @staticmethod
    def _new_state() -> Dict[str, Any]:
        """Create new state object"""
        return {
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "stages": {
                "research": {"complete": False, "timestamp": None, "error": None},
                "story": {"complete": False, "timestamp": None, "error": None},
                "art": {"complete": False, "timestamp": None, "error": None},
                "pdf": {"complete": False, "timestamp": None, "error": None},
                "publish": {"complete": False, "timestamp": None, "error": None},
            }
        }

    def mark_complete(self, stage: str, success: bool = True, error: str = None):
        """Mark a stage as complete or failed"""
        if stage in self.state["stages"]:
            self.state["stages"][stage]["complete"] = success
            self.state["stages"][stage]["timestamp"] = datetime.now().isoformat()
            if error:
                self.state["stages"][stage]["error"] = error
            self.state["updated_at"] = datetime.now().isoformat()
            self._save_state()

    def is_complete(self, stage: str) -> bool:
        """Check if a stage is complete"""
        return self.state["stages"].get(stage, {}).get("complete", False)

    def _save_state(self):
        """Save state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def get_summary(self) -> str:
        """Get human-readable state summary"""
        lines = []
        for stage, info in self.state["stages"].items():
            status = "✓" if info["complete"] else "○"
            lines.append(f"  {status} {stage.ljust(10)} {info.get('error', 'OK')}")
        return "\n".join(lines)


class BookFactory:
    """Main orchestrator for the book publishing pipeline"""

    def __init__(self, config: ConfigLoader, args: argparse.Namespace):
        """Initialize the book factory"""
        self.config = config
        self.args = args
        self.base_output_dir = Path("output")
        self.base_output_dir.mkdir(exist_ok=True)

    def run(self):
        """Execute the pipeline based on arguments"""
        print_header("BOOK FACTORY STUDIO")
        print_info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            if self.args.research_only:
                self._run_research_only()
            elif self.args.art_only:
                self._run_art_only()
            elif self.args.pdf_only:
                self._run_pdf_only()
            elif self.args.batch:
                self._run_batch()
            elif self.args.from_brief:
                self._run_from_brief()
            else:
                self._run_full_pipeline()
        except KeyboardInterrupt:
            print_warning("\nPipeline interrupted by user")
            sys.exit(130)
        except Exception as e:
            print_error(f"Fatal error: {e}")
            logger.exception("Fatal error in pipeline")
            sys.exit(1)

    def _run_full_pipeline(self):
        """Run complete pipeline: research -> story -> art -> pdf -> publish"""
        book_id = BookID.generate()
        output_dir = self.base_output_dir / book_id

        print_header(f"FULL PIPELINE: {book_id}")
        print_info(f"Output directory: {output_dir}")

        state = PipelineState(output_dir)

        try:
            # Stage 1: Research
            self._run_stage(
                state, "research",
                lambda: self._stage_research(output_dir),
                "Niche Research"
            )

            # Stage 2: Story Generation
            self._run_stage(
                state, "story",
                lambda: self._stage_story(output_dir),
                "Story Generation"
            )

            # Stage 3: Art Generation
            if not self.args.no_publish:
                self._run_stage(
                    state, "art",
                    lambda: self._stage_art(output_dir, book_id),
                    "Art Generation (Mac)"
                )

            # Stage 4: PDF Generation
            if not self.args.no_publish:
                self._run_stage(
                    state, "pdf",
                    lambda: self._stage_pdf(output_dir),
                    "PDF Generation"
                )

            # Stage 5: KDP Publishing
            if not self.args.no_publish:
                self._run_stage(
                    state, "publish",
                    lambda: self._stage_publish(output_dir),
                    "KDP Publishing"
                )

            print_header("PIPELINE COMPLETE")
            print_success(f"Book '{book_id}' generated successfully!")
            print_info(f"Output: {output_dir}")
            print("\nPipeline Status:")
            print(state.get_summary())

        except Exception as e:
            print_error(f"Pipeline failed: {e}")
            logger.exception("Pipeline error")
            raise

    def _run_research_only(self):
        """Run only the research stage"""
        book_id = BookID.generate()
        output_dir = self.base_output_dir / book_id

        print_header("RESEARCH ONLY")
        print_info(f"Output directory: {output_dir}")

        state = PipelineState(output_dir)
        self._run_stage(
            state, "research",
            lambda: self._stage_research(output_dir),
            "Niche Research"
        )

        print_success("Research complete!")
        print_info(f"Results saved to {output_dir}")

    def _run_from_brief(self):
        """Run pipeline starting from a brief JSON file"""
        brief_path = Path(self.args.from_brief)

        if not brief_path.exists():
            print_error(f"Brief file not found: {brief_path}")
            sys.exit(1)

        try:
            with open(brief_path, 'r') as f:
                brief = json.load(f)
        except Exception as e:
            print_error(f"Failed to load brief: {e}")
            sys.exit(1)

        book_id = BookID.generate(brief.get("niche", "unknown"))
        output_dir = self.base_output_dir / book_id

        print_header(f"FROM BRIEF: {book_id}")
        print_info(f"Brief: {brief_path}")
        print_info(f"Output directory: {output_dir}")

        state = PipelineState(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save brief
        brief_out = output_dir / "brief.json"
        with open(brief_out, 'w') as f:
            json.dump(brief, f, indent=2)
        print_success(f"Loaded brief from {brief_path}")

        # Run remaining stages
        self._run_stage(
            state, "story",
            lambda: self._stage_story(output_dir),
            "Story Generation"
        )

        if not self.args.no_publish:
            self._run_stage(
                state, "art",
                lambda: self._stage_art(output_dir, book_id),
                "Art Generation (Mac)"
            )

            self._run_stage(
                state, "pdf",
                lambda: self._stage_pdf(output_dir),
                "PDF Generation"
            )

            self._run_stage(
                state, "publish",
                lambda: self._stage_publish(output_dir),
                "KDP Publishing"
            )

        print_success("Pipeline complete!")

    def _run_batch(self):
        """Generate multiple books from top niches"""
        num_books = self.args.batch
        print_header(f"BATCH MODE: {num_books} Books")

        book_ids = []

        for i in range(num_books):
            book_num = i + 1
            print_info(f"\n[{book_num}/{num_books}] Generating book {book_num}...")

            book_id = BookID.generate()
            output_dir = self.base_output_dir / book_id
            book_ids.append((book_id, output_dir))

            state = PipelineState(output_dir)

            try:
                self._run_stage(
                    state, "research",
                    lambda: self._stage_research(output_dir),
                    f"Research (Book {book_num})"
                )

                self._run_stage(
                    state, "story",
                    lambda: self._stage_story(output_dir),
                    f"Story (Book {book_num})"
                )

                print_success(f"Book {book_num} ready for art generation")

            except Exception as e:
                print_error(f"Book {book_num} failed: {e}")
                logger.exception(f"Error generating book {book_num}")

        print_header("BATCH GENERATION COMPLETE")
        print_info(f"Generated {len(book_ids)} books:")
        for book_id, output_dir in book_ids:
            print_info(f"  - {book_id}")
            print_info(f"    Output: {output_dir}")

    def _run_art_only(self):
        """Regenerate art for an existing book"""
        book_id = self.args.art_only
        output_dir = self.base_output_dir / book_id

        if not output_dir.exists():
            print_error(f"Book not found: {output_dir}")
            sys.exit(1)

        print_header(f"ART REGENERATION: {book_id}")

        state = PipelineState(output_dir)
        self._run_stage(
            state, "art",
            lambda: self._stage_art(output_dir, book_id),
            "Art Generation (Mac)"
        )

        print_success("Art regeneration complete!")

    def _run_pdf_only(self):
        """Rebuild PDFs for an existing book"""
        book_id = self.args.pdf_only
        output_dir = self.base_output_dir / book_id

        if not output_dir.exists():
            print_error(f"Book not found: {output_dir}")
            sys.exit(1)

        print_header(f"PDF REBUILD: {book_id}")

        state = PipelineState(output_dir)
        self._run_stage(
            state, "pdf",
            lambda: self._stage_pdf(output_dir),
            "PDF Generation"
        )

        print_success("PDF rebuild complete!")

    def _run_stage(self, state: PipelineState, stage_name: str,
                   stage_func, display_name: str):
        """Run a pipeline stage with error handling and resume capability"""
        if state.is_complete(stage_name):
            print_info(f"{display_name}: SKIPPED (already complete)")
            return

        print_step(
            list(state.state["stages"].keys()).index(stage_name) + 1,
            len(state.state["stages"]),
            display_name
        )

        try:
            start_time = time.time()
            result = stage_func()
            elapsed = time.time() - start_time

            state.mark_complete(stage_name, success=True)
            print_success(f"{display_name} complete ({elapsed:.1f}s)")
            return result

        except Exception as e:
            error_msg = str(e)
            state.mark_complete(stage_name, success=False, error=error_msg)
            print_error(f"{display_name} failed: {error_msg}")
            raise

    def _stage_research(self, output_dir: Path) -> Dict[str, Any]:
        """Stage 1: Niche Research"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Placeholder for research module
        brief = {
            "niche": "Ocean Animals - Sea Turtles",
            "age_range": "3-6",
            "estimated_bsr": 45000,
            "competition_score": 35,
            "keywords": ["sea turtle", "ocean", "animals", "conservation", "children"],
            "story_theme": "A young sea turtle's first journey to the ocean",
            "timestamp": datetime.now().isoformat()
        }

        brief_path = output_dir / "brief.json"
        with open(brief_path, 'w') as f:
            json.dump(brief, f, indent=2)

        print_info(f"Niche: {brief['niche']}")
        print_info(f"Age Range: {brief['age_range']}")
        print_info(f"Competition Score: {brief['competition_score']}/100")

        return brief

    def _stage_story(self, output_dir: Path) -> Dict[str, Any]:
        """Stage 2: Story Generation"""
        output_dir.mkdir(parents=True, exist_ok=True)

        brief_path = output_dir / "brief.json"
        if not brief_path.exists():
            raise FileNotFoundError(f"Brief not found: {brief_path}")

        with open(brief_path, 'r') as f:
            brief = json.load(f)

        # Placeholder for story generation
        story_package = {
            "title": "Shelly's Ocean Journey",
            "subtitle": "A Tale of Discovery and Wonder",
            "niche": brief.get("niche"),
            "age_range": brief.get("age_range"),
            "character_names": ["Shelly", "Ocean", "Reef Friends"],
            "story_outline": [
                "Introduction: Shelly is born on a warm beach",
                "Rising action: Shelly's first glimpse of the ocean",
                "Climax: Shelly braves the waves to begin her journey",
                "Resolution: Shelly discovers her home in the reef"
            ],
            "pages": 24,
            "story_text": {
                "page_1": "Once upon a time, on a warm sandy beach...",
                "page_2": "Shelly the sea turtle hatched from her egg...",
            },
            "character_descriptions": {
                "Shelly": "A brave young sea turtle with a curious spirit. Soft shell, warm brown eyes with bright highlights.",
                "Ocean": "Personified as a gentle, welcoming guide. Blue and green tones, flowing form.",
            },
            "art_prompts": {
                "page_1": "A baby sea turtle hatching from sand on a peaceful beach at sunrise",
                "page_2": "Shelly the sea turtle looking out at the vast ocean, amazed and excited",
            },
            "keywords": brief.get("keywords", []),
            "timestamp": datetime.now().isoformat()
        }

        story_path = output_dir / "story_package.json"
        with open(story_path, 'w') as f:
            json.dump(story_package, f, indent=2)

        print_info(f"Title: {story_package['title']}")
        print_info(f"Pages: {story_package['pages']}")
        print_info(f"Age Range: {story_package['age_range']}")

        return story_package

    def _stage_art(self, output_dir: Path, book_id: str) -> Dict[str, Any]:
        """Stage 3: Art Generation (runs on Mac)"""
        output_dir.mkdir(parents=True, exist_ok=True)
        art_dir = output_dir / "art"
        art_dir.mkdir(exist_ok=True)

        # Generate Mac script
        mac_script_path = Path("scripts") / f"run_on_mac_{book_id}.py"
        mac_script_path.parent.mkdir(exist_ok=True)

        mac_script = self._generate_mac_script(output_dir, book_id)
        with open(mac_script_path, 'w') as f:
            f.write(mac_script)

        os.chmod(mac_script_path, 0o755)

        print_info(f"Generated Mac script: {mac_script_path}")
        print_warning("Art generation requires manual execution on Mac")
        print_warning(f"Run: python3 {mac_script_path}")

        # Create placeholder result
        art_result = {
            "book_id": book_id,
            "status": "pending_mac_execution",
            "mac_script": str(mac_script_path),
            "instructions": "Run the Mac script to generate images with OpenAI API",
            "timestamp": datetime.now().isoformat()
        }

        result_path = output_dir / "art_result.json"
        with open(result_path, 'w') as f:
            json.dump(art_result, f, indent=2)

        return art_result

    def _generate_mac_script(self, output_dir: Path, book_id: str) -> str:
        """Generate the Mac-side art generation script"""
        script = f'''#!/usr/bin/env python3
"""
Art Generation Script for {book_id}
Run this on your Mac to generate illustrations using OpenAI DALL-E

Usage:
    python3 {Path('scripts') / f'run_on_mac_{book_id}.py'}
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
output_dir = Path("{output_dir}")
story_path = output_dir / "story_package.json"
art_dir = output_dir / "art"

if not story_path.exists():
    print(f"Error: Story file not found: {{story_path}}")
    sys.exit(1)

# Load story
with open(story_path, 'r') as f:
    story = json.load(f)

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

# Create art directory
art_dir.mkdir(exist_ok=True)

print(f"Generating illustrations for {{story['title']}}...")
print(f"Output directory: {{art_dir}}")

# Generate images for each page
generated_images = {{}}
for page_num in range(1, story.get('pages', 24) + 1):
    page_key = f"page_{{page_num}}"

    if page_key not in story.get('art_prompts', {{}}):
        print(f"Skipping {{page_key}}: no prompt defined")
        continue

    prompt = story['art_prompts'][page_key]
    art_style = "Soft gouache/watercolor painting. Warm, textured, hand-painted look."
    full_prompt = f"{{prompt}}\\n\\nStyle: {{art_style}}"

    print(f"\\nGenerating {{page_key}}...")
    print(f"Prompt: {{prompt[:60]}}...")

    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=full_prompt,
            size="1024x1024",
            quality="hd",
            n=1
        )

        image_url = response.data[0].url
        image_path = art_dir / f"{{page_key}}.json"

        image_data = {{
            "page": page_num,
            "prompt": prompt,
            "url": image_url,
            "model": "dall-e-3",
            "generated_at": datetime.now().isoformat()
        }}

        with open(image_path, 'w') as f:
            json.dump(image_data, f, indent=2)

        generated_images[page_key] = {{
            "url": image_url,
            "path": str(image_path)
        }}

        print(f"✓ Generated {{page_key}}")

    except Exception as e:
        print(f"✗ Failed to generate {{page_key}}: {{e}}")

# Save summary
summary = {{
    "book_id": "{book_id}",
    "title": story.get('title'),
    "total_pages": story.get('pages'),
    "generated_count": len(generated_images),
    "generated_at": datetime.now().isoformat(),
    "images": generated_images
}}

summary_path = art_dir / "generation_summary.json"
with open(summary_path, 'w') as f:
    json.dump(summary, f, indent=2)

print(f"\\n✓ Art generation complete!")
print(f"Generated {{len(generated_images)}} images")
print(f"Summary saved to: {{summary_path}}")
print(f"\\nNext steps:")
print(f"1. Review images in {{art_dir}}")
print(f"2. Upload the entire 'art' folder back to the sandbox")
print(f"3. Run: python3 studio.py --pdf-only {book_id}")
'''
        return script

    def _stage_pdf(self, output_dir: Path) -> Dict[str, Any]:
        """Stage 4: PDF Generation"""
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_dir = output_dir / "pdfs"
        pdf_dir.mkdir(exist_ok=True)

        story_path = output_dir / "story_package.json"
        if not story_path.exists():
            raise FileNotFoundError(f"Story not found: {story_path}")

        with open(story_path, 'r') as f:
            story = json.load(f)

        # Placeholder for PDF generation
        pdf_result = {
            "book_id": story.get("title"),
            "pages": story.get("pages"),
            "paperback_pdf": str(pdf_dir / "paperback.pdf"),
            "ebook_pdf": str(pdf_dir / "ebook.pdf"),
            "cover_pdf": str(pdf_dir / "cover.pdf"),
            "trim_size": self.config.get("defaults.trim_size"),
            "status": "ready_for_publishing",
            "timestamp": datetime.now().isoformat()
        }

        result_path = output_dir / "pdf_result.json"
        with open(result_path, 'w') as f:
            json.dump(pdf_result, f, indent=2)

        print_info(f"Title: {story['title']}")
        print_info(f"Trim Size: {self.config.get('defaults.trim_size')}")
        print_info(f"PDFs: {len([f for f in pdf_dir.glob('*.pdf')])}")

        return pdf_result

    def _stage_publish(self, output_dir: Path) -> Dict[str, Any]:
        """Stage 5: KDP Publishing"""
        output_dir.mkdir(parents=True, exist_ok=True)

        story_path = output_dir / "story_package.json"
        if not story_path.exists():
            raise FileNotFoundError(f"Story not found: {story_path}")

        with open(story_path, 'r') as f:
            story = json.load(f)

        # Check for KDP credentials
        kdp_email = self.config.get("kdp.email")
        kdp_password = self.config.get("kdp.password")

        if not kdp_email or not kdp_password:
            print_warning("KDP credentials not configured")
            print_warning("Set kdp.email and kdp.password in config/studio_config.yaml")
            publish_result = {
                "status": "skipped_no_credentials",
                "message": "Configure KDP credentials to enable publishing",
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Placeholder for actual KDP publishing
            publish_result = {
                "status": "published",
                "asin": "B0DUMMY001",
                "title": story.get("title"),
                "url": "https://www.amazon.com/dp/B0DUMMY001",
                "timestamp": datetime.now().isoformat()
            }
            print_info(f"Published: {story['title']}")
            print_info(f"ASIN: {publish_result['asin']}")

        result_path = output_dir / "publish_result.json"
        with open(result_path, 'w') as f:
            json.dump(publish_result, f, indent=2)

        return publish_result


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Book Factory Studio - Automated Children's Book Publishing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 studio.py                           # Full pipeline
  python3 studio.py --research-only           # Just run research
  python3 studio.py --from-brief brief.json   # Generate from brief
  python3 studio.py --batch 5                 # Generate 5 books
  python3 studio.py --no-publish              # Everything except publish
  python3 studio.py --art-only book-id        # Regenerate art
  python3 studio.py --pdf-only book-id        # Rebuild PDFs
        """
    )

    parser.add_argument(
        "--research-only",
        action="store_true",
        help="Run only niche research stage"
    )

    parser.add_argument(
        "--from-brief",
        type=str,
        help="Skip research, generate from brief JSON file"
    )

    parser.add_argument(
        "--batch",
        type=int,
        help="Generate N books from top niches"
    )

    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Run everything except KDP publishing"
    )

    parser.add_argument(
        "--art-only",
        type=str,
        help="Regenerate art for existing book ID"
    )

    parser.add_argument(
        "--pdf-only",
        type=str,
        help="Rebuild PDFs for existing book ID"
    )

    parser.add_argument(
        "--config",
        type=str,
        help="Path to custom config file (default: config/studio_config.yaml)"
    )

    args = parser.parse_args()

    # Load config
    config = ConfigLoader(args.config)

    # Create and run factory
    factory = BookFactory(config, args)
    factory.run()


if __name__ == "__main__":
    main()
