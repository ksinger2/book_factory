#!/usr/bin/env python3
"""
Book Factory Studio — Local Web Server
Double-click or run `python3 run.py` to start.
Opens http://localhost:5555 in your browser.
"""

import json
import os
import sys
import time
import threading
import webbrowser
import logging
import platform
from pathlib import Path
from datetime import datetime
from queue import Queue

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify, send_from_directory, Response, send_file
import yaml

# ─── App Setup ───
app = Flask(__name__, static_folder='.', static_url_path='')
app.config['SECRET_KEY'] = 'book-factory-local'

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config" / "studio_config.yaml"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Organized subdirectories for different book types
CHILDRENS_OUTPUT_DIR = OUTPUT_DIR / "ChildrensBook"
CHILDRENS_OUTPUT_DIR.mkdir(exist_ok=True)
COLORING_OUTPUT_DIR = OUTPUT_DIR / "ColoringBook"
COLORING_OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger("studio")

# Global progress queue for SSE
progress_queues: dict = {}


def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


def save_config(cfg):
    CONFIG_PATH.parent.mkdir(exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)


def find_chrome_profile():
    system = platform.system()
    home = os.path.expanduser("~")
    paths = {
        "Darwin": [f"{home}/Library/Application Support/Google/Chrome"],
        "Linux": [f"{home}/.config/google-chrome", f"{home}/.config/chromium"],
        "Windows": [f"{os.environ.get('LOCALAPPDATA', '')}/Google/Chrome/User Data"],
    }
    for p in paths.get(system, []):
        if Path(p).exists():
            return p
    return None


# ─── API Routes ───

@app.route('/')
def index():
    return send_file(BASE_DIR / 'dashboard.html')


@app.route('/api/status')
def api_status():
    """Check system readiness — API keys, Chrome profile, deps."""
    anthropic_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    openai_key = bool(os.environ.get("OPENAI_API_KEY"))
    chrome = find_chrome_profile()
    cfg = load_config()

    # Check which deps are installed
    deps = {}
    for mod in ['openai', 'anthropic', 'reportlab', 'PIL', 'playwright', 'bs4']:
        try:
            __import__(mod)
            deps[mod] = True
        except ImportError:
            deps[mod] = False

    return jsonify({
        "anthropic_key": anthropic_key,
        "openai_key": openai_key,
        "chrome_profile": bool(chrome),
        "chrome_path": chrome,
        "config": cfg,
        "deps": deps,
        "output_dir": str(OUTPUT_DIR),
    })


@app.route('/api/config', methods=['POST'])
def api_config():
    """Save configuration."""
    data = request.json
    cfg = load_config()
    # Deep merge
    for key, val in data.items():
        if isinstance(val, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(val)
        else:
            cfg[key] = val
    save_config(cfg)
    return jsonify({"ok": True})


@app.route('/api/marketing/analyze', methods=['POST'])
def api_marketing_analyze():
    """Run full marketing analysis for a book."""
    try:
        from agents.kdp_marketing import KDPMarketingAgent

        data = request.json or {}
        book_id = data.get("book_id")

        if not book_id:
            return jsonify({"ok": False, "error": "No book_id provided"}), 400

        book_dir = OUTPUT_DIR / book_id
        if not book_dir.exists():
            return jsonify({"ok": False, "error": "Book not found"}), 404

        agent = KDPMarketingAgent()
        result = agent.run(str(book_dir))

        # Convert dataclass to dict for JSON serialization
        from dataclasses import asdict
        return jsonify({"ok": True, "result": asdict(result)})

    except Exception as e:
        log.exception("Marketing analysis failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/marketing/keywords', methods=['POST'])
def api_marketing_keywords():
    """Quick keyword-only analysis."""
    try:
        from agents.kdp_marketing import KDPMarketingAgent

        data = request.json or {}
        book_id = data.get("book_id")

        if not book_id:
            return jsonify({"ok": False, "error": "No book_id provided"}), 400

        book_dir = OUTPUT_DIR / book_id
        if not book_dir.exists():
            return jsonify({"ok": False, "error": "Book not found"}), 404

        agent = KDPMarketingAgent()
        book_data = agent._load_book_data(str(book_dir))
        keywords = agent.analyze_keywords(book_data)

        from dataclasses import asdict
        return jsonify({
            "ok": True,
            "keywords": [asdict(kw) for kw in keywords]
        })

    except Exception as e:
        log.exception("Keyword analysis failed")
        return jsonify({"ok": False, "error": str(e)}), 500


def get_debug_mode():
    """Get debug mode from environment variable or config."""
    import os
    # Environment variable takes precedence
    env_debug = os.environ.get('BOOK_FACTORY_DEBUG', '').lower()
    if env_debug in ('true', '1', 'yes'):
        return True
    if env_debug in ('false', '0', 'no'):
        return False
    # Fall back to config
    cfg = load_config()
    return cfg.get('global', {}).get('debug_mode', False)


@app.route('/api/story', methods=['POST'])
def api_story():
    """Generate a story from a brief."""
    try:
        from agents.story_engine import StoryEngine

        brief = request.json
        if not brief:
            return jsonify({"ok": False, "error": "No brief provided"}), 400

        # Check for debug mode
        debug_mode = get_debug_mode()
        if debug_mode:
            log.info("Story generation running in DEBUG MODE (using gpt-4o-mini)")

        engine = StoryEngine(debug_mode=debug_mode)
        result = engine.run(brief)

        # Save to output dir - use book title for directory name
        title = result.get("story", {}).get("title", "untitled")
        # Sanitize title for use as directory name
        safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)
        safe_title = safe_title.strip().replace(" ", "_")[:50]  # Limit length
        if not safe_title:
            safe_title = "untitled"
        # Add timestamp suffix to ensure uniqueness
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        book_id = f"ChildrensBook/{safe_title}-{timestamp}"
        book_dir = OUTPUT_DIR / book_id
        book_dir.mkdir(parents=True, exist_ok=True)

        with open(book_dir / "story_package.json", 'w') as f:
            json.dump(result, f, indent=2, default=str)

        with open(book_dir / "brief.json", 'w') as f:
            json.dump(brief, f, indent=2)

        return jsonify({"ok": True, "book_id": book_id, "story": result})
    except Exception as e:
        log.exception("Story generation failed")
        return jsonify({"ok": False, "error": str(e)}), 500


# Track cancelled jobs
cancelled_jobs = set()

@app.route('/api/art/cancel', methods=['POST'])
def api_art_cancel():
    """Cancel an art generation job."""
    data = request.json
    book_id = data.get("book_id")
    if book_id:
        cancelled_jobs.add(book_id)
        log.info(f"Art generation cancelled for {book_id}")
        return jsonify({"ok": True, "message": "Cancellation requested"})
    return jsonify({"ok": False, "error": "No book_id provided"}), 400

@app.route('/api/art', methods=['POST'])
def api_art():
    """Generate illustrations with SSE progress updates."""
    data = request.json
    book_id = data.get("book_id")
    if not book_id:
        return jsonify({"ok": False, "error": "No book_id provided"}), 400

    # Clear any previous cancellation for this job
    cancelled_jobs.discard(book_id)

    book_dir = OUTPUT_DIR / book_id
    story_path = book_dir / "story_package.json"

    if not story_path.exists():
        return jsonify({"ok": False, "error": "Story package not found. Generate story first."}), 400

    with open(story_path) as f:
        story_data = json.load(f)

    # Transform story data to art pipeline format
    story = story_data.get('story', story_data)
    character = story_data.get('character', {})
    scenes = story.get('scenes', [])
    metadata = story_data.get('metadata', {})
    brief = metadata.get('brief', {})

    # Get art style and user notes from brief
    art_style = brief.get('art_style', '')
    user_notes = brief.get('notes', '')
    theme = brief.get('theme', '')

    # Get eye style from brief or config
    eye_style = brief.get('eye_style', '')
    if not eye_style:
        # Try to get from config
        cfg = load_config()
        eye_style = cfg.get('art', {}).get('eye_style', '')

    # Get reference image if provided (base64 data URL)
    reference_image = brief.get('reference_image', '')

    # Build character description for consistency across all images
    char_name = character.get('name', 'the main character')
    char_desc = character.get('description', '')
    char_species = character.get('species', '')

    # Character consistency block - included in EVERY prompt
    character_block = f"\n\nMain character: {char_name}"
    if char_species:
        character_block += f" (a {char_species})"
    if char_desc:
        character_block += f". {char_desc}"

    # User restrictions block
    restrictions = ""
    if user_notes:
        restrictions += f"\n\nIMPORTANT: {user_notes}"
    if "no people" in user_notes.lower() or "no human" in user_notes.lower():
        restrictions += " Only show the animal character(s), no humans."

    # Hard rules from brief (apply to ALL image prompts, NOT story)
    hard_rules = brief.get('hard_rules', '').strip()

    # Build prompts with style, character, restrictions, and hard rules
    def build_prompt(base_prompt):
        prompt = base_prompt
        # Inject hard rules at the TOP - must be followed strictly
        if hard_rules:
            prompt = f"=== STRICT RULES - MUST FOLLOW ===\n{hard_rules}\n=== END STRICT RULES ===\n\n{prompt}"
        if art_style:
            # Extract just the positive style elements (remove any NOT statements)
            style_clean = ' '.join([s for s in art_style.split('.') if 'NOT' not in s.upper()])
            prompt = f"{style_clean}\n\n{prompt}"
        prompt += character_block
        prompt += restrictions
        return prompt

    # Add eye style to character description if specified
    char_description = build_prompt(character.get('sheet_prompt', character.get('description', '')))
    if eye_style:
        char_description += f"\n\nEYE STYLE: {eye_style}"

    # Build spreads with full context (illustration prompt + page text)
    spreads_with_context = []
    for i, scene in enumerate(scenes):
        page_text = "\n".join(scene.get('text', []))
        illustration_prompt = build_prompt(scene.get('illustration_prompt', ''))
        spreads_with_context.append({
            "page_num": i + 1,
            "illustration_prompt": illustration_prompt,
            "page_text": page_text
        })

    art_package = {
        "title": story.get('title', 'Untitled'),
        "character_name": character.get('name', 'Character'),
        "character_description": char_description,
        "cover_scene": build_prompt(scenes[0].get('illustration_prompt', '')) if scenes else '',
        "spreads": spreads_with_context,
        "back_cover_scene": build_prompt(scenes[-1].get('illustration_prompt', '')) if scenes else '',
        "art_style": art_style,
        "eye_style": eye_style,
        "character_block": character_block,
        "restrictions": restrictions,
        "reference_image": reference_image,
        "hard_rules": hard_rules
    }

    art_dir = book_dir / "art"
    art_dir.mkdir(exist_ok=True)

    def generate_with_progress():
        from agents.art_pipeline import ArtPipeline
        import time

        total_images = 2 + len(art_package['spreads'])  # char sheet + cover + spreads + back
        current = 0

        try:
            # Check for debug mode
            debug_mode = get_debug_mode()
            if debug_mode:
                log.info("Art generation running in DEBUG MODE (using dall-e-2, skipping QA)")

            # Initialize pipeline with art style, eye style, reference image, and hard rules from the brief
            art_style_for_pipeline = art_package.get('art_style', '')
            eye_style_for_pipeline = art_package.get('eye_style', '')
            reference_image_for_pipeline = art_package.get('reference_image', '')
            hard_rules_for_pipeline = art_package.get('hard_rules', '')
            pipeline = ArtPipeline(
                style=art_style_for_pipeline,
                eye_style=eye_style_for_pipeline,
                reference_image=reference_image_for_pipeline,
                hard_rules=hard_rules_for_pipeline,
                debug_mode=debug_mode
            )
            results = {
                "success": False,
                "character_sheet": None,
                "cover": None,
                "spreads": [],
                "back_cover": None,
                "failed_images": []
            }

            # Character sheets (main + recurring characters)
            current += 1
            yield f"data: {json.dumps({'stage': 'character_sheet', 'current': current, 'total': total_images, 'message': 'Generating character sheet...'})}\n\n"

            char_sheet_path = art_dir / "character_sheets" / f"{art_package['character_name']}_sheet.png"
            char_sheet_path.parent.mkdir(parents=True, exist_ok=True)
            char_name = art_package["character_name"]
            all_character_sheets = {}  # Store all character sheets

            try:
                _, char_path = pipeline.generate_character_sheet(
                    art_package["character_description"],
                    char_sheet_path,
                    style=art_style_for_pipeline
                )
                results["character_sheet"] = str(char_path)
                all_character_sheets[char_name] = char_path
                yield f"data: {json.dumps({'stage': 'character_sheet_done', 'current': current, 'total': total_images, 'message': 'Character sheet complete!', 'image_path': f'character_sheets/{char_name}_sheet.png'})}\n\n"

                # Extract recurring characters from scenes
                spreads = art_package.get('spreads', [])
                if spreads:
                    yield f"data: {json.dumps({'stage': 'analyzing_characters', 'current': current, 'total': total_images, 'message': 'Analyzing scenes for recurring characters...'})}\n\n"
                    recurring_chars = pipeline.extract_recurring_characters(spreads, char_name)

                    # Generate sheets for recurring characters
                    for rc_name, rc_info in recurring_chars.items():
                        yield f"data: {json.dumps({'stage': 'secondary_character', 'current': current, 'total': total_images, 'message': f'Generating character sheet for {rc_name}...'})}\n\n"
                        try:
                            safe_name = "".join(c if c.isalnum() else "_" for c in rc_name)
                            rc_sheet_path = art_dir / "character_sheets" / f"{safe_name}_sheet.png"

                            rc_desc = f"""Secondary character for children's book:
Name: {rc_name}
Description: {rc_info['description']}

This character appears alongside {char_name} in scenes {rc_info['scenes']}.
Create a consistent character sheet showing various poses and expressions."""

                            _, rc_path = pipeline.generate_character_sheet(
                                rc_desc,
                                rc_sheet_path,
                                style=art_style_for_pipeline
                            )
                            all_character_sheets[rc_name] = rc_path
                            yield f"data: {json.dumps({'stage': 'secondary_character_done', 'current': current, 'total': total_images, 'message': f'{rc_name} character sheet complete!', 'image_path': f'character_sheets/{safe_name}_sheet.png'})}\n\n"
                        except Exception as e:
                            log.warning(f"Failed to generate character sheet for {rc_name}: {e}")
                            yield f"data: {json.dumps({'stage': 'secondary_character_error', 'current': current, 'total': total_images, 'message': f'{rc_name} sheet failed: {str(e)}'})}\n\n"

            except Exception as e:
                results["failed_images"].append(f"character_sheet: {str(e)}")
                yield f"data: {json.dumps({'stage': 'character_sheet_error', 'current': current, 'total': total_images, 'message': f'Character sheet failed: {str(e)}'})}\n\n"
                char_path = None

            # Store all character sheets in results
            results["all_character_sheets"] = {name: str(path) for name, path in all_character_sheets.items()}

            # Cover
            current += 1
            yield f"data: {json.dumps({'stage': 'cover', 'current': current, 'total': total_images, 'message': 'Generating cover illustration...'})}\n\n"

            if char_path and art_package.get('cover_scene'):
                cover_path = art_dir / "cover.png"
                try:
                    _, cpath = pipeline.generate_illustration(
                        art_package["cover_scene"],
                        char_path,
                        illustration_type="cover",
                        output_path=cover_path,
                        style=art_style_for_pipeline
                    )
                    results["cover"] = str(cpath)
                    yield f"data: {json.dumps({'stage': 'cover_done', 'current': current, 'total': total_images, 'message': 'Cover complete!', 'image_path': 'cover.png'})}\n\n"
                except Exception as e:
                    results["failed_images"].append(f"cover: {str(e)}")
                    yield f"data: {json.dumps({'stage': 'cover_error', 'current': current, 'total': total_images, 'message': f'Cover failed: {str(e)}'})}\n\n"

            # Spreads (scenes)
            spreads = art_package.get('spreads', [])
            story_title = art_package.get('title', 'Untitled')
            char_block = art_package.get('character_block', '')

            for i, spread_data in enumerate(spreads):
                # Check for cancellation
                if book_id in cancelled_jobs:
                    yield f"data: {json.dumps({'stage': 'cancelled', 'current': current, 'total': total_images, 'message': 'Generation cancelled by user'})}\n\n"
                    cancelled_jobs.discard(book_id)
                    return

                current += 1
                yield f"data: {json.dumps({'stage': 'spread', 'current': current, 'total': total_images, 'message': f'Generating illustration {i+1} of {len(spreads)}...'})}\n\n"

                # Build full context for this page
                if isinstance(spread_data, dict):
                    spread_desc = spread_data.get('illustration_prompt', '')
                    page_text = spread_data.get('page_text', '')
                    page_num = spread_data.get('page_num', i + 1)
                else:
                    # Backwards compatibility
                    spread_desc = spread_data
                    page_text = ''
                    page_num = i + 1

                # Add story context to the prompt
                story_context = f"""
=== STORY CONTEXT ===
Book Title: {story_title}
Page {page_num} of {len(spreads)}
{char_block}

Page Text (the verse for this illustration):
{page_text}

=== ILLUSTRATION FOR THIS PAGE ===
{spread_desc}"""

                if char_path and spread_desc:
                    spread_path = art_dir / f"scene_{i+1:02d}.png"
                    try:
                        _, spath = pipeline.generate_illustration(
                            story_context,
                            char_path,
                            illustration_type="spread",
                            output_path=spread_path,
                            style=art_style_for_pipeline
                        )
                        results["spreads"].append(str(spath))
                        yield f"data: {json.dumps({'stage': 'spread_done', 'current': current, 'total': total_images, 'message': f'Illustration {i+1} complete!', 'image_path': f'scene_{i+1:02d}.png'})}\n\n"
                    except Exception as e:
                        results["failed_images"].append(f"spread_{i+1}: {str(e)}")
                        yield f"data: {json.dumps({'stage': 'spread_error', 'current': current, 'total': total_images, 'message': f'Illustration {i+1} failed: {str(e)}'})}\n\n"

            results["success"] = len(results["failed_images"]) == 0

            # Save result
            result_path = book_dir / "art_result.json"
            with open(result_path, 'w') as f:
                json.dump(results, f, indent=2, default=str)

            yield f"data: {json.dumps({'stage': 'complete', 'current': total_images, 'total': total_images, 'message': 'Art generation complete!', 'result': results})}\n\n"

        except Exception as e:
            log.exception("Art generation failed")
            yield f"data: {json.dumps({'stage': 'error', 'message': str(e)})}\n\n"

    return Response(generate_with_progress(), mimetype='text/event-stream')


@app.route('/api/charsheet', methods=['POST'])
def api_charsheet():
    """Generate just the character sheet with SSE progress."""
    data = request.json
    book_id = data.get("book_id")
    guidance = data.get("guidance", "").strip()
    guidance_reference_image = data.get("guidance_reference_image")
    if not book_id:
        return jsonify({"ok": False, "error": "No book_id provided"}), 400

    book_dir = OUTPUT_DIR / book_id
    story_path = book_dir / "story_package.json"

    if not story_path.exists():
        return jsonify({"ok": False, "error": "Story package not found. Generate story first."}), 400

    with open(story_path) as f:
        story_data = json.load(f)

    # Extract data needed for character sheet
    character = story_data.get('character', {})
    metadata = story_data.get('metadata', {})
    brief = metadata.get('brief', {})

    art_style = brief.get('art_style', '')
    eye_style = brief.get('eye_style', '')
    reference_image = brief.get('reference_image', '')
    hard_rules = brief.get('hard_rules', '')

    # Build character description
    char_desc = character.get('sheet_prompt', character.get('description', ''))
    if art_style:
        style_clean = ' '.join([s for s in art_style.split('.') if 'NOT' not in s.upper()])
        char_desc = f"{style_clean}\n\n{char_desc}"
    if eye_style:
        char_desc += f"\n\nEYE STYLE: {eye_style}"

    char_name = character.get('name', 'Character')

    art_dir = book_dir / "art"
    art_dir.mkdir(exist_ok=True)

    def generate_charsheet():
        import threading
        from agents.art_pipeline import ArtPipeline

        result_box = {"char_path": None, "visual_guide": None, "error": None, "done": False}

        def run_generation():
            try:
                debug_mode = get_debug_mode()
                if debug_mode:
                    log.info("Character sheet generation running in DEBUG MODE")

                pipeline = ArtPipeline(
                    style=art_style,
                    eye_style=eye_style,
                    reference_image=reference_image,
                    hard_rules=hard_rules,
                    debug_mode=debug_mode
                )

                char_sheet_path = art_dir / "character_sheets" / f"{char_name}_sheet.png"
                char_sheet_path.parent.mkdir(parents=True, exist_ok=True)

                _, char_path = pipeline.generate_character_sheet(
                    char_desc,
                    char_sheet_path,
                    style=art_style,
                    guidance=guidance,
                    guidance_reference=guidance_reference_image
                )

                result_box["char_path"] = char_path
                result_box["visual_guide"] = getattr(pipeline, 'character_visual_guide', '')
            except Exception as e:
                log.exception("Character sheet generation failed")
                result_box["error"] = str(e)
            finally:
                result_box["done"] = True

        yield f"data: {json.dumps({'stage': 'charsheet_start', 'message': 'Generating character sheet...'})}\n\n"

        t = threading.Thread(target=run_generation, daemon=True)
        t.start()

        heartbeat_count = 0
        while not result_box["done"]:
            time.sleep(5)
            heartbeat_count += 1
            yield f"data: {json.dumps({'stage': 'charsheet_working', 'message': f'Still generating... ({heartbeat_count * 5}s)'})}\n\n"

        t.join(timeout=5)

        if result_box["error"]:
            yield f"data: {json.dumps({'stage': 'charsheet_error', 'message': result_box['error']})}\n\n"
            return

        char_path = result_box["char_path"]

        # Save character visual guide for later use by illustrations
        art_result_path = book_dir / "art_result.json"
        art_result = {}
        if art_result_path.exists():
            with open(art_result_path) as f:
                art_result = json.load(f)

        art_result["character_sheet"] = str(char_path)
        art_result["character_visual_guide"] = result_box["visual_guide"] or ''

        with open(art_result_path, 'w') as f:
            json.dump(art_result, f, indent=2, default=str)

        image_path = f"character_sheets/{char_name}_sheet.png"
        yield f"data: {json.dumps({'stage': 'charsheet_done', 'message': 'Character sheet complete!', 'image_path': image_path})}\n\n"

    return Response(generate_charsheet(), mimetype='text/event-stream')


@app.route('/api/charsheet/approve', methods=['POST'])
def api_charsheet_approve():
    """Approve the character sheet to enable illustration generation."""
    data = request.json
    book_id = data.get("book_id")

    if not book_id:
        return jsonify({"ok": False, "error": "No book_id provided"}), 400

    book_dir = OUTPUT_DIR / book_id
    char_sheet_dir = book_dir / "art" / "character_sheets"

    # Verify character sheet exists
    if not char_sheet_dir.exists() or not list(char_sheet_dir.glob("*.png")):
        return jsonify({"ok": False, "error": "No character sheet found. Generate one first."}), 400

    # Create approval marker
    approval_marker = book_dir / ".charsheet_approved"
    approval_marker.touch()

    log.info(f"Character sheet approved for {book_id}")
    return jsonify({"ok": True, "message": "Character sheet approved"})


@app.route('/api/approve-image', methods=['POST'])
def api_approve_image():
    """Approve an image in debug mode to continue generation to the next image."""
    data = request.json
    book_id = data.get("book_id")
    image_type = data.get("image_type", "spread")  # 'cover', 'spread', or 'page'
    index = data.get("index", 1)  # For spreads/pages, which number

    if not book_id:
        return jsonify({"ok": False, "error": "No book_id provided"}), 400

    book_dir = OUTPUT_DIR / book_id
    if not book_dir.exists():
        return jsonify({"ok": False, "error": "Book not found"}), 404

    # Determine approval marker filename based on image type
    if image_type == 'cover':
        approval_marker = book_dir / ".cover_approved"
    elif image_type == 'spread':
        approval_marker = book_dir / f".spread_{index:02d}_approved"
    elif image_type == 'page':
        approval_marker = book_dir / f".page_{index:02d}_approved"
    else:
        return jsonify({"ok": False, "error": f"Unknown image_type: {image_type}"}), 400

    # Create approval marker
    approval_marker.touch()

    log.info(f"Image approved in debug mode: {book_id}/{image_type}/{index}")
    return jsonify({"ok": True, "message": f"{image_type.capitalize()} {index} approved"})


@app.route('/api/illustrations', methods=['POST'])
def api_illustrations():
    """Generate illustrations (cover + spreads) with SSE progress. Requires approved character sheet."""
    data = request.json
    book_id = data.get("book_id")
    if not book_id:
        return jsonify({"ok": False, "error": "No book_id provided"}), 400

    # Check for debug mode from config or request
    cfg = load_config()
    debug_mode = data.get("debug_mode", cfg.get('art', {}).get('debug_mode', False))

    # Clear any previous cancellation
    cancelled_jobs.discard(book_id)

    book_dir = OUTPUT_DIR / book_id

    # Check for character sheet approval
    approval_marker = book_dir / ".charsheet_approved"
    if not approval_marker.exists():
        return jsonify({
            "ok": False,
            "error": "Character sheet not approved. Please approve before generating illustrations."
        }), 403

    story_path = book_dir / "story_package.json"
    if not story_path.exists():
        return jsonify({"ok": False, "error": "Story package not found."}), 400

    with open(story_path) as f:
        story_data = json.load(f)

    # Load art result with character sheet info
    art_result_path = book_dir / "art_result.json"
    if not art_result_path.exists():
        return jsonify({"ok": False, "error": "Character sheet not found. Generate it first."}), 400

    with open(art_result_path) as f:
        art_result = json.load(f)

    char_sheet = art_result.get("character_sheet")
    if not char_sheet:
        return jsonify({"ok": False, "error": "Character sheet path not found."}), 400

    # Extract data
    story = story_data.get('story', story_data)
    character = story_data.get('character', {})
    scenes = story.get('scenes', [])
    metadata = story_data.get('metadata', {})
    brief = metadata.get('brief', {})

    art_style = brief.get('art_style', '')
    eye_style = brief.get('eye_style', '')
    reference_image = brief.get('reference_image', '')
    user_notes = brief.get('notes', '')

    # Build character block
    char_name = character.get('name', 'the main character')
    char_desc = character.get('description', '')
    char_species = character.get('species', '')

    character_block = f"\n\nMain character: {char_name}"
    if char_species:
        character_block += f" (a {char_species})"
    if char_desc:
        character_block += f". {char_desc}"

    restrictions = ""
    if user_notes:
        restrictions += f"\n\nIMPORTANT: {user_notes}"
        if "no people" in user_notes.lower() or "no human" in user_notes.lower():
            restrictions += " Only show the animal character(s), no humans."

    # Hard rules from brief (apply to ALL image prompts, NOT story)
    hard_rules = brief.get('hard_rules', '').strip()

    def build_prompt(base_prompt):
        prompt = base_prompt
        # Inject hard rules at the TOP - must be followed strictly
        if hard_rules:
            prompt = f"=== STRICT RULES - MUST FOLLOW ===\n{hard_rules}\n=== END STRICT RULES ===\n\n{prompt}"
        if art_style:
            style_clean = ' '.join([s for s in art_style.split('.') if 'NOT' not in s.upper()])
            prompt = f"{style_clean}\n\n{prompt}"
        prompt += character_block
        prompt += restrictions
        return prompt

    # Build spreads with context
    spreads_with_context = []
    for i, scene in enumerate(scenes):
        page_text = "\n".join(scene.get('text', []))
        illustration_prompt = build_prompt(scene.get('illustration_prompt', ''))
        spreads_with_context.append({
            "page_num": i + 1,
            "illustration_prompt": illustration_prompt,
            "page_text": page_text
        })

    art_dir = book_dir / "art"
    art_dir.mkdir(exist_ok=True)

    def generate_illustrations():
        from agents.art_pipeline import ArtPipeline

        total_images = 1 + len(spreads_with_context)  # cover + spreads
        current = 0

        try:
            # Check for debug mode (from request or config)
            art_debug_mode = get_debug_mode()
            if art_debug_mode:
                log.info("Illustration generation running in DEBUG MODE")

            pipeline = ArtPipeline(
                style=art_style,
                eye_style=eye_style,
                reference_image=reference_image,
                hard_rules=hard_rules,
                debug_mode=art_debug_mode
            )

            # Load character visual guide if available
            visual_guide = art_result.get("character_visual_guide", "")
            if visual_guide:
                pipeline.character_visual_guide = visual_guide

            char_path = Path(char_sheet)

            # Cover
            current += 1
            yield f"data: {json.dumps({'stage': 'generating', 'current': current, 'total': total_images, 'message': 'Generating cover illustration...'})}\n\n"

            cover_scene = build_prompt(scenes[0].get('illustration_prompt', '')) if scenes else ''
            if cover_scene:
                cover_path = art_dir / "cover.png"
                try:
                    _, cpath = pipeline.generate_illustration(
                        cover_scene,
                        char_path,
                        illustration_type="cover",
                        output_path=cover_path,
                        style=art_style
                    )
                    art_result["cover"] = str(cpath)
                    yield f"data: {json.dumps({'stage': 'image_done', 'current': current, 'total': total_images, 'message': 'Cover complete!', 'image_path': 'cover.png', 'image_type': 'cover', 'debug_mode': debug_mode})}\n\n"

                    # Debug mode: wait for approval before continuing
                    if debug_mode:
                        approval_file = book_dir / ".cover_approved"
                        # Remove any existing approval marker
                        if approval_file.exists():
                            approval_file.unlink()
                        yield f"data: {json.dumps({'stage': 'awaiting_approval', 'current': current, 'total': total_images, 'message': 'Cover ready - waiting for approval...', 'image_type': 'cover', 'image_path': 'cover.png'})}\n\n"
                        while not approval_file.exists():
                            if book_id in cancelled_jobs:
                                yield f"data: {json.dumps({'stage': 'cancelled', 'current': current, 'total': total_images, 'message': 'Generation cancelled by user'})}\n\n"
                                cancelled_jobs.discard(book_id)
                                return
                            time.sleep(0.5)
                        yield f"data: {json.dumps({'stage': 'approved', 'current': current, 'total': total_images, 'message': 'Cover approved! Continuing...', 'image_type': 'cover'})}\n\n"

                except Exception as e:
                    yield f"data: {json.dumps({'stage': 'image_error', 'current': current, 'total': total_images, 'message': f'Cover failed: {str(e)}'})}\n\n"

            # Spreads
            story_title = story.get('title', 'Untitled')
            art_result["spreads"] = []

            for i, spread_data in enumerate(spreads_with_context):
                # Check for cancellation
                if book_id in cancelled_jobs:
                    yield f"data: {json.dumps({'stage': 'cancelled', 'current': current, 'total': total_images, 'message': 'Generation cancelled by user'})}\n\n"
                    cancelled_jobs.discard(book_id)
                    return

                current += 1
                yield f"data: {json.dumps({'stage': 'generating', 'current': current, 'total': total_images, 'message': f'Generating illustration {i+1} of {len(spreads_with_context)}...'})}\n\n"

                spread_desc = spread_data.get('illustration_prompt', '')
                page_text = spread_data.get('page_text', '')
                page_num = spread_data.get('page_num', i + 1)

                story_context = f"""
=== STORY CONTEXT ===
Book Title: {story_title}
Page {page_num} of {len(spreads_with_context)}
{character_block}

Page Text (the verse for this illustration):
{page_text}

=== ILLUSTRATION FOR THIS PAGE ===
{spread_desc}"""

                spread_path = art_dir / f"scene_{i+1:02d}.png"
                try:
                    _, spath = pipeline.generate_illustration(
                        story_context,
                        char_path,
                        illustration_type="spread",
                        output_path=spread_path,
                        style=art_style
                    )
                    art_result["spreads"].append(str(spath))
                    yield f"data: {json.dumps({'stage': 'image_done', 'current': current, 'total': total_images, 'message': f'Illustration {i+1} complete!', 'image_path': f'scene_{i+1:02d}.png', 'image_type': 'spread', 'index': i+1, 'debug_mode': debug_mode})}\n\n"

                    # Debug mode: wait for approval before generating next spread
                    if debug_mode:
                        approval_file = book_dir / f".spread_{i+1:02d}_approved"
                        # Remove any existing approval marker
                        if approval_file.exists():
                            approval_file.unlink()
                        yield f"data: {json.dumps({'stage': 'awaiting_approval', 'current': current, 'total': total_images, 'message': f'Spread {i+1} ready - waiting for approval...', 'image_type': 'spread', 'image_path': f'scene_{i+1:02d}.png', 'index': i+1})}\n\n"
                        while not approval_file.exists():
                            if book_id in cancelled_jobs:
                                yield f"data: {json.dumps({'stage': 'cancelled', 'current': current, 'total': total_images, 'message': 'Generation cancelled by user'})}\n\n"
                                cancelled_jobs.discard(book_id)
                                return
                            time.sleep(0.5)
                        yield f"data: {json.dumps({'stage': 'approved', 'current': current, 'total': total_images, 'message': f'Spread {i+1} approved! Continuing...', 'image_type': 'spread', 'index': i+1})}\n\n"

                except Exception as e:
                    yield f"data: {json.dumps({'stage': 'image_error', 'current': current, 'total': total_images, 'message': f'Illustration {i+1} failed: {str(e)}'})}\n\n"

            # Save updated art result
            art_result["success"] = True
            with open(art_result_path, 'w') as f:
                json.dump(art_result, f, indent=2, default=str)

            yield f"data: {json.dumps({'stage': 'complete', 'current': total_images, 'total': total_images, 'message': 'All illustrations complete!'})}\n\n"

        except Exception as e:
            log.exception("Illustration generation failed")
            yield f"data: {json.dumps({'stage': 'error', 'message': str(e)})}\n\n"

    return Response(generate_illustrations(), mimetype='text/event-stream')


@app.route('/api/story/update', methods=['POST'])
def api_story_update():
    """Update story scene text."""
    try:
        data = request.json
        book_id = data.get("book_id")
        scene_index = data.get("scene_index")  # 0-based
        new_text = data.get("text")  # Array of lines

        if not book_id:
            return jsonify({"ok": False, "error": "No book_id provided"}), 400
        if scene_index is None:
            return jsonify({"ok": False, "error": "No scene_index provided"}), 400

        book_dir = OUTPUT_DIR / book_id
        story_path = book_dir / "story_package.json"

        if not story_path.exists():
            return jsonify({"ok": False, "error": "Story not found"}), 404

        with open(story_path) as f:
            story_data = json.load(f)

        # Update the scene text
        story = story_data.get('story', story_data)
        scenes = story.get('scenes', [])

        if scene_index < 0 or scene_index >= len(scenes):
            return jsonify({"ok": False, "error": "Invalid scene index"}), 400

        scenes[scene_index]['text'] = new_text

        # Save back to file
        with open(story_path, 'w') as f:
            json.dump(story_data, f, indent=2, default=str)

        log.info(f"Updated scene {scene_index + 1} text for {book_id}")
        return jsonify({"ok": True, "message": "Scene updated"})

    except Exception as e:
        log.exception("Story update failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/regenerate-image', methods=['POST'])
def api_regenerate_image():
    """Regenerate a single image with optional feedback."""
    try:
        from agents.art_pipeline import ArtPipeline

        data = request.json
        book_id = data.get("book_id")
        image_type = data.get("image_type")  # 'spread', 'cover', 'character_sheet'
        scene_index = data.get("scene_index", 1)  # 1-based
        feedback = data.get("feedback", "")  # User feedback for regeneration
        use_current_as_reference = data.get("use_current_as_reference", False)
        additional_references = data.get("additional_references", [])  # Extra reference image URLs

        if not book_id:
            return jsonify({"ok": False, "error": "No book_id provided"}), 400
        if not image_type:
            return jsonify({"ok": False, "error": "No image_type provided"}), 400

        book_dir = OUTPUT_DIR / book_id
        art_dir = book_dir / "art"
        story_path = book_dir / "story_package.json"

        if not story_path.exists():
            return jsonify({"ok": False, "error": "Story not found"}), 404

        with open(story_path) as f:
            story_data = json.load(f)

        # Get story and character info
        story = story_data.get('story', story_data)
        scenes = story.get('scenes', [])
        character = story_data.get('character', {})
        metadata = story_data.get('metadata', {})
        brief = metadata.get('brief', {})
        art_style = brief.get('art_style', '')
        hard_rules = brief.get('hard_rules', '')

        # Find character sheet path
        char_name = character.get('name', 'Character')
        char_sheet_path = art_dir / "character_sheets" / f"{char_name}_sheet.png"

        if not char_sheet_path.exists():
            # Try to find any character sheet
            char_sheets_dir = art_dir / "character_sheets"
            if char_sheets_dir.exists():
                sheets = list(char_sheets_dir.glob("*.png"))
                if sheets:
                    char_sheet_path = sheets[0]
                else:
                    return jsonify({"ok": False, "error": "No character sheet found. Generate art first."}), 400
            else:
                return jsonify({"ok": False, "error": "No character sheet found. Generate art first."}), 400

        # Convert additional reference URLs to local paths
        extra_refs = []
        for ref_url in additional_references:
            # URLs like /api/files/ChildrensBook/Title-123/art/scene_01.png
            if ref_url.startswith('/api/files/'):
                rel_path = ref_url.replace('/api/files/', '')
                local_path = OUTPUT_DIR / rel_path
                if local_path.exists():
                    extra_refs.append(local_path)
                    log.info(f"Added additional reference: {local_path}")

        # Load art_result.json to get character_visual_guide
        art_result_path = art_dir / 'art_result.json'
        character_visual_guide = None
        if art_result_path.exists():
            try:
                with open(art_result_path) as f:
                    art_result = json.load(f)
                    character_visual_guide = art_result.get('character_visual_guide', '')
                    if character_visual_guide:
                        log.info(f"Loaded character visual guide for regeneration: {character_visual_guide[:100]}...")
            except Exception as e:
                log.warning(f"Could not load art_result.json: {e}")

        # Initialize pipeline with character visual guide and debug mode
        regen_debug_mode = get_debug_mode()
        pipeline = ArtPipeline(style=art_style, hard_rules=hard_rules, debug_mode=regen_debug_mode)
        if character_visual_guide:
            pipeline.character_visual_guide = character_visual_guide

        if image_type == 'spread':
            if scene_index < 1 or scene_index > len(scenes):
                return jsonify({"ok": False, "error": "Invalid scene index"}), 400

            scene = scenes[scene_index - 1]  # Convert to 0-based
            scene_desc = scene.get('illustration_prompt', '')
            output_path = art_dir / f"scene_{scene_index:02d}.png"

            # Add feedback to description if provided
            if feedback:
                scene_desc = f"{scene_desc}\n\n=== USER FEEDBACK FOR REGENERATION ===\n{feedback}\n=== END FEEDBACK ==="

            # Add note about additional references
            if extra_refs:
                scene_desc += f"\n\n*** ADDITIONAL STYLE REFERENCES ***\nUse the {len(extra_refs)} additional reference images to match style and consistency."

            # Choose reference image: current image or character sheet
            reference_image = output_path if use_current_as_reference and output_path.exists() else char_sheet_path

            # Use fix_image method with additional references
            success, result = pipeline.fix_image(
                f"scene_{scene_index:02d}.png",
                reference_image,
                scene_desc,
                illustration_type="spread",
                output_dir=book_dir,
                style=art_style,
                additional_references=extra_refs
            )

            if success:
                return jsonify({
                    "ok": True,
                    "message": f"Scene {scene_index} regenerated",
                    "image_path": f"scene_{scene_index:02d}.png"
                })
            else:
                error_msg = result
                if 'moderation' in error_msg.lower() or 'content_policy' in error_msg.lower():
                    error_msg = "Content moderation blocked this image. Try adjusting your feedback text to avoid trigger words, or modify the scene description."
                return jsonify({"ok": False, "error": error_msg}), 500

        elif image_type == 'cover':
            cover_scene = scenes[0].get('illustration_prompt', '') if scenes else ''
            output_path = art_dir / "cover.png"

            # Add feedback to description if provided
            if feedback:
                cover_scene = f"{cover_scene}\n\n=== USER FEEDBACK FOR REGENERATION ===\n{feedback}\n=== END FEEDBACK ==="

            # Add note about additional references
            if extra_refs:
                cover_scene += f"\n\n*** ADDITIONAL STYLE REFERENCES ***\nUse the {len(extra_refs)} additional reference images to match style and consistency."

            # Choose reference image: current image or character sheet
            reference_image = output_path if use_current_as_reference and output_path.exists() else char_sheet_path

            _, _ = pipeline.generate_illustration(
                cover_scene,
                reference_image,
                illustration_type="cover",
                output_path=output_path,
                style=art_style,
                additional_references=extra_refs
            )

            return jsonify({
                "ok": True,
                "message": "Cover regenerated",
                "image_path": "cover.png"
            })

        elif image_type == 'character_sheet':
            char_desc = character.get('sheet_prompt', character.get('description', ''))
            output_path = char_sheet_path

            # Add feedback to description if provided
            if feedback:
                char_desc = f"{char_desc}\n\n=== USER FEEDBACK FOR REGENERATION ===\n{feedback}\n=== END FEEDBACK ==="

            _, _ = pipeline.generate_character_sheet(
                char_desc,
                output_path,
                style=art_style
            )

            return jsonify({
                "ok": True,
                "message": "Character sheet regenerated",
                "image_path": f"character_sheets/{char_name}_sheet.png"
            })

        else:
            return jsonify({"ok": False, "error": f"Unknown image type: {image_type}"}), 400

    except Exception as e:
        log.exception("Image regeneration failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/pdf', methods=['POST'])
def api_pdf():
    """Build PDFs from story + art."""
    try:
        from agents.pdf_builder import PDFBuilder, StoryPackage, StoryPage, TextOverlay

        data = request.json
        book_id = data.get("book_id")
        if not book_id:
            return jsonify({"ok": False, "error": "No book_id"}), 400

        book_dir = OUTPUT_DIR / book_id
        story_path = book_dir / "story_package.json"
        art_dir = book_dir / "art"

        if not story_path.exists():
            return jsonify({"ok": False, "error": "Story not found"}), 400

        with open(story_path) as f:
            story_data = json.load(f)

        # Convert dict to StoryPackage dataclass
        cfg = load_config()
        story_content = story_data.get('story', story_data)
        listing = story_data.get('listing', {})

        # Build pages from scenes
        pages = []
        scenes = story_content.get('scenes', [])
        for i, scene in enumerate(scenes):
            text = scene.get('text', [])
            if isinstance(text, list):
                text = '\n'.join(text)
            pages.append(StoryPage(
                image_path=f"scene_{i+1:02d}.png",
                text_overlays=[TextOverlay(
                    text=text,
                    x=4.25,
                    y=7.0,
                    font_size=14
                )]
            ))

        story_package = StoryPackage(
            title=story_content.get('title', 'Untitled'),
            author=cfg.get('defaults', {}).get('author_name', 'Unknown Author'),
            subtitle=listing.get('subtitle', ''),
            blurb=listing.get('description', ''),
            pages=pages
        )

        builder = PDFBuilder()
        result = builder.build_all(story_package, str(art_dir), str(book_dir))

        return jsonify({"ok": True, "book_id": book_id, "result": result})
    except Exception as e:
        log.exception("PDF build failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/publish', methods=['POST'])
def api_publish():
    """Publish to KDP using Chrome profile."""
    try:
        from agents.kdp_publisher import KDPPublisher, BookPackage, BookListing

        data = request.json
        book_id = data.get("book_id")
        dry_run = data.get("dry_run", False)  # Set to True for testing without submitting

        if not book_id:
            return jsonify({"ok": False, "error": "No book_id"}), 400

        book_dir = OUTPUT_DIR / book_id
        story_path = book_dir / "story_package.json"

        # Check required files exist
        interior_pdf = book_dir / "Interior.pdf"
        cover_pdf = book_dir / "Cover.pdf"
        kindle_cover = book_dir / "Kindle_Cover.jpg"

        missing = []
        if not story_path.exists():
            missing.append("story_package.json")
        if not interior_pdf.exists():
            missing.append("Interior.pdf")
        if not cover_pdf.exists():
            missing.append("Cover.pdf")
        if not kindle_cover.exists():
            missing.append("Kindle_Cover.jpg")

        if missing:
            return jsonify({"ok": False, "error": f"Missing files: {', '.join(missing)}. Run 'Build PDFs' first."}), 400

        # Load story data
        with open(story_path) as f:
            story_data = json.load(f)

        story = story_data.get('story', story_data)
        listing_data = story_data.get('listing', {})
        cfg = load_config()

        # Build BookListing
        book_listing = BookListing(
            title=listing_data.get('title', story.get('title', 'Untitled')),
            subtitle=listing_data.get('subtitle', ''),
            author=cfg.get('defaults', {}).get('author_name', 'Unknown Author'),
            description=listing_data.get('description', ''),
            categories=listing_data.get('categories', ['Children\'s Books > Animals']),
            keywords=listing_data.get('keywords', [])[:7],  # Max 7 keywords
            ai_disclosure_text="Entire work, with extensive editing",
            ai_tool_text="Claude",
            ai_disclosure_images="Many AI-generated images, with extensive editing",
            ai_tool_images="ChatGPT",
            ai_disclosure_translation="None"
        )

        # Build BookPackage
        book_package = BookPackage(
            listing=book_listing,
            interior_pdf_path=str(interior_pdf),
            cover_pdf_path=str(cover_pdf),
            cover_jpg_path=str(kindle_cover),
            us_price=cfg.get('defaults', {}).get('us_price', 9.99),
            is_kdp_select=True,
            dry_run=dry_run
        )

        # Start publisher and publish
        log.info(f"Starting KDP publish for: {book_listing.title}")
        use_chrome = cfg.get('kdp', {}).get('use_chrome_profile', False)
        chrome_profile_name = cfg.get('kdp', {}).get('chrome_profile_name', 'Profile 2')
        try:
            with KDPPublisher(use_chrome_profile=use_chrome, chrome_profile_name=chrome_profile_name) as publisher:
                result = publisher.publish_book(book_package)
            return jsonify({"ok": True, "book_id": book_id, "result": result})
        except Exception as browser_error:
            error_msg = str(browser_error)
            if "ProcessSingleton" in error_msg or "profile directory" in error_msg:
                return jsonify({
                    "ok": False,
                    "error": "Chrome is currently running. Please close ALL Chrome windows and try again. The publisher needs exclusive access to your Chrome profile to use your Amazon login."
                }), 400
            raise

    except Exception as e:
        log.exception("Publish failed")
        return jsonify({"ok": False, "error": str(e)}), 500


# ─── Coloring Book API Routes ───

@app.route('/api/coloring/generate-title', methods=['POST'])
def api_coloring_generate_title():
    """Generate a creative title for a coloring book based on theme."""
    try:
        from openai import OpenAI
        client = OpenAI()

        data = request.json
        theme = data.get('theme', 'General')

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"""Generate a creative, catchy title for a coloring book with the theme: "{theme}"

Requirements:
- Short and memorable (2-5 words)
- Appealing to the target audience
- Works well on a book cover
- Alliteration or rhyme is a plus

Return ONLY the title, nothing else. No quotes, no explanation."""
            }],
            max_tokens=50,
            temperature=0.9
        )

        title = response.choices[0].message.content.strip().strip('"').strip("'")
        return jsonify({"ok": True, "title": title})

    except Exception as e:
        log.exception("Title generation failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/coloring/brief', methods=['POST'])
def api_coloring_brief():
    """Save coloring book configuration and create book_id."""
    try:
        brief = request.json
        if not brief:
            return jsonify({"ok": False, "error": "No brief provided"}), 400

        # Validate theme is not empty
        theme = brief.get('theme', '').strip()
        if not theme:
            return jsonify({"ok": False, "error": "Theme is required"}), 400
        brief['theme'] = theme

        # Create book directory in ColoringBook subdirectory
        title = brief.get('title', 'Coloring Book')
        safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)
        safe_title = safe_title.strip().replace(" ", "_")[:50] or "coloring_book"
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        book_id = f"ColoringBook/{safe_title}-{timestamp}"
        book_dir = OUTPUT_DIR / book_id
        book_dir.mkdir(parents=True, exist_ok=True)

        # Save brief
        with open(book_dir / "coloring_brief.json", 'w') as f:
            json.dump(brief, f, indent=2)

        log.info(f"Coloring book brief saved: {book_id}")
        return jsonify({"ok": True, "book_id": book_id, "brief": brief})

    except Exception as e:
        log.exception("Coloring brief save failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/coloring/reference', methods=['POST'])
def api_coloring_reference():
    """Generate reference/style sheet for coloring book."""
    try:
        from agents.coloring_style_generator import ColoringStyleGenerator, StyleBrief

        data = request.json
        book_id = data.get("book_id")
        feedback = data.get("feedback", "")  # User feedback for regeneration
        draft_mode = data.get("draft_mode", False)  # Use cheaper models for testing
        if not book_id:
            return jsonify({"ok": False, "error": "No book_id provided"}), 400

        book_dir = OUTPUT_DIR / book_id
        brief_path = book_dir / "coloring_brief.json"

        if not brief_path.exists():
            return jsonify({"ok": False, "error": "Brief not found. Save brief first."}), 400

        with open(brief_path) as f:
            brief_data = json.load(f)

        # Debug logging for style
        log.info(f"=== COLORING REFERENCE DEBUG ===")
        log.info(f"brief_data keys: {list(brief_data.keys())}")
        log.info(f"brief_data['style']: {brief_data.get('style', 'NOT FOUND - defaulting to bold-easy')}")
        if feedback:
            log.info(f"feedback: {feedback}")
        log.info(f"=== END DEBUG ===")

        # Create style brief with fallback for empty theme
        theme = brief_data.get('theme', '').strip() or 'General'

        # Combine notes with feedback if provided
        notes = brief_data.get('notes', '')
        if feedback:
            notes = f"{notes}\n\n=== USER FEEDBACK FOR REGENERATION ===\n{feedback}\n=== END FEEDBACK ===" if notes else f"=== USER FEEDBACK FOR REGENERATION ===\n{feedback}\n=== END FEEDBACK ==="

        style_brief = StyleBrief(
            theme=theme,
            age_level=brief_data.get('ageLevel', 'adult'),
            difficulty=brief_data.get('difficulty', 'medium'),
            notes=notes,
            reference_image=brief_data.get('referenceImage'),
            style=brief_data.get('style', 'bold-easy')
        )

        # Generate reference sheet - combine draft_mode from request with global debug_mode
        effective_draft_mode = draft_mode or get_debug_mode()
        generator = ColoringStyleGenerator(draft_mode=effective_draft_mode)
        output_path = book_dir / "reference_sheet.png"
        success, path = generator.generate_reference_sheet(style_brief, output_path)

        if success:
            # Generate page concepts
            num_pages = brief_data.get('numPages', 24)
            concepts = generator.generate_page_concepts(style_brief, num_pages)

            # Save concepts
            with open(book_dir / "page_concepts.json", 'w') as f:
                json.dump(concepts, f, indent=2)

            return jsonify({
                "ok": True,
                "book_id": book_id,
                "reference_sheet": f"{book_id}/reference_sheet.png",
                "concepts": concepts
            })
        else:
            return jsonify({"ok": False, "error": "Reference sheet generation failed"}), 500

    except Exception as e:
        log.exception("Reference sheet generation failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/coloring/reference/approve', methods=['POST'])
def api_coloring_reference_approve():
    """Mark reference sheet as approved."""
    try:
        data = request.json
        book_id = data.get("book_id")
        if not book_id:
            return jsonify({"ok": False, "error": "No book_id provided"}), 400

        book_dir = OUTPUT_DIR / book_id
        ref_path = book_dir / "reference_sheet.png"

        if not ref_path.exists():
            return jsonify({"ok": False, "error": "Reference sheet not found"}), 400

        # Save approval status
        status_path = book_dir / ".reference_approved"
        status_path.touch()

        log.info(f"Reference sheet approved for {book_id}")
        return jsonify({"ok": True, "message": "Reference sheet approved"})

    except Exception as e:
        log.exception("Reference approval failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/coloring/cancel', methods=['POST'])
def api_coloring_cancel():
    """Cancel ongoing coloring page generation."""
    try:
        data = request.json
        book_id = data.get("book_id")
        if book_id:
            cancelled_jobs.add(book_id)
            log.info(f"Coloring generation cancelled for {book_id}")
            return jsonify({"ok": True, "message": "Cancellation requested"})
        return jsonify({"ok": False, "error": "No book_id provided"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/coloring/pages', methods=['POST'])
def api_coloring_pages():
    """Generate all coloring pages with SSE progress updates."""
    data = request.json
    book_id = data.get("book_id")
    if not book_id:
        return jsonify({"ok": False, "error": "No book_id provided"}), 400

    # Check for debug mode from config or request
    cfg = load_config()
    debug_mode = data.get("debug_mode", cfg.get('coloring', {}).get('debug_mode', False))

    # Clear any previous cancellation for this book (allows retry after cancel)
    cancelled_jobs.discard(book_id)

    book_dir = OUTPUT_DIR / book_id
    brief_path = book_dir / "coloring_brief.json"
    ref_path = book_dir / "reference_sheet.png"
    concepts_path = book_dir / "page_concepts.json"

    if not brief_path.exists():
        return jsonify({"ok": False, "error": "Brief not found"}), 400
    if not ref_path.exists():
        return jsonify({"ok": False, "error": "Reference sheet not found. Generate it first."}), 400

    # Check that reference sheet was approved before generating pages
    approval_marker = book_dir / ".reference_approved"
    if not approval_marker.exists():
        return jsonify({
            "ok": False,
            "error": "Reference sheet not approved. Please approve the style sheet before generating pages."
        }), 403

    with open(brief_path) as f:
        brief_data = json.load(f)

    # Load concepts if available
    concepts = []
    if concepts_path.exists():
        with open(concepts_path) as f:
            concepts = json.load(f)

    # Get draft mode from request
    draft_mode = data.get("draft_mode", False)

    def generate_pages_with_progress():
        from agents.coloring_page_generator import ColoringPageGenerator, PageConfig
        from agents.coloring_qa_checker import ColoringQAChecker

        num_pages = brief_data.get('numPages', 24)
        theme = brief_data.get('theme', 'General')
        age_level = brief_data.get('ageLevel', 'adult')
        difficulty = brief_data.get('difficulty', 'medium')
        style = brief_data.get('style', 'bold-easy')
        notes = brief_data.get('notes', '')

        pages_dir = book_dir / "pages"
        pages_dir.mkdir(exist_ok=True)

        # Combine draft_mode from request with global debug_mode
        effective_draft_mode = draft_mode or get_debug_mode()
        generator = ColoringPageGenerator(draft_mode=effective_draft_mode)
        qa_checker = ColoringQAChecker()

        results = {
            "success": True,
            "pages": [],
            "failed_pages": []
        }

        # Track generated subjects for uniqueness enforcement
        generated_subjects = []

        def extract_subject(concept_str):
            """Extract primary subject from concept string."""
            skip_words = {'a', 'an', 'the', 'large', 'small', 'big', 'tiny', 'cute', 'beautiful',
                          'majestic', 'friendly', 'happy', 'single', 'one', 'two', 'decorated'}
            words = concept_str.lower().split()
            for word in words:
                clean_word = ''.join(c for c in word if c.isalnum())
                if clean_word and clean_word not in skip_words and len(clean_word) > 2:
                    return clean_word
            return words[0] if words else "unknown"

        for i in range(num_pages):
            # Check for cancellation
            if book_id in cancelled_jobs:
                yield f"data: {json.dumps({'stage': 'cancelled', 'current': i, 'total': num_pages, 'message': 'Generation cancelled'})}\n\n"
                cancelled_jobs.discard(book_id)
                return

            page_num = i + 1
            concept = concepts[i] if i < len(concepts) else f"{theme} design {page_num}"

            yield f"data: {json.dumps({'stage': 'generating', 'current': page_num, 'total': num_pages, 'message': f'Generating page {page_num}...'})}\n\n"

            config = PageConfig(
                page_num=page_num,
                concept=concept,
                theme=theme,
                age_level=age_level,
                difficulty=difficulty,
                style=style,
                notes=notes,
                previous_subjects=generated_subjects.copy()
            )

            output_path = pages_dir / f"page_{page_num:02d}.png"
            max_attempts = 3
            qa_passed = False

            for attempt in range(max_attempts):
                # Check for cancellation before each generation attempt
                if book_id in cancelled_jobs:
                    yield f"data: {json.dumps({'stage': 'cancelled', 'current': page_num, 'total': num_pages, 'message': 'Generation cancelled by user'})}\n\n"
                    cancelled_jobs.discard(book_id)
                    return

                success, path = generator.generate_page(config, ref_path, output_path)

                # Check for cancellation immediately after generation
                if book_id in cancelled_jobs:
                    yield f"data: {json.dumps({'stage': 'cancelled', 'current': page_num, 'total': num_pages, 'message': 'Generation cancelled by user'})}\n\n"
                    cancelled_jobs.discard(book_id)
                    return

                if success:
                    # Run QA check
                    yield f"data: {json.dumps({'stage': 'qa_check', 'current': page_num, 'total': num_pages, 'message': f'QA checking page {page_num}...'})}\n\n"

                    qa_result = qa_checker.check_page(path, age_level, difficulty, theme)

                    if qa_result.passed:
                        qa_passed = True
                        # Track this subject for uniqueness in subsequent pages
                        generated_subjects.append(extract_subject(concept))
                        results["pages"].append({
                            "page_num": page_num,
                            "path": str(path),
                            "qa_passed": True,
                            "qa_scores": qa_result.scores
                        })
                        yield f"data: {json.dumps({'stage': 'page_done', 'current': page_num, 'total': num_pages, 'message': f'Page {page_num} complete!', 'image_path': f'pages/page_{page_num:02d}.png', 'qa_passed': True, 'debug_mode': debug_mode})}\n\n"

                        # Debug mode: wait for approval before generating next page
                        if debug_mode:
                            approval_file = book_dir / f".page_{page_num:02d}_approved"
                            # Remove any existing approval marker
                            if approval_file.exists():
                                approval_file.unlink()
                            yield f"data: {json.dumps({'stage': 'awaiting_approval', 'current': page_num, 'total': num_pages, 'message': f'Page {page_num} ready - waiting for approval...', 'image_type': 'page', 'image_path': f'pages/page_{page_num:02d}.png', 'index': page_num})}\n\n"
                            while not approval_file.exists():
                                if book_id in cancelled_jobs:
                                    yield f"data: {json.dumps({'stage': 'cancelled', 'current': page_num, 'total': num_pages, 'message': 'Generation cancelled by user'})}\n\n"
                                    cancelled_jobs.discard(book_id)
                                    return
                                time.sleep(0.5)
                            yield f"data: {json.dumps({'stage': 'approved', 'current': page_num, 'total': num_pages, 'message': f'Page {page_num} approved! Continuing...', 'image_type': 'page', 'index': page_num})}\n\n"

                        break
                    else:
                        yield f"data: {json.dumps({'stage': 'qa_retry', 'current': page_num, 'total': num_pages, 'message': f'Page {page_num} QA failed, retrying ({attempt + 1}/{max_attempts})...'})}\n\n"

            if not qa_passed:
                results["failed_pages"].append(page_num)
                results["pages"].append({
                    "page_num": page_num,
                    "path": str(output_path) if output_path.exists() else None,
                    "qa_passed": False,
                    "error": "Failed QA after max retries"
                })
                yield f"data: {json.dumps({'stage': 'page_failed', 'current': page_num, 'total': num_pages, 'message': f'Page {page_num} failed after {max_attempts} attempts'})}\n\n"

        results["success"] = len(results["failed_pages"]) == 0

        # Save results
        with open(book_dir / "pages_result.json", 'w') as f:
            json.dump(results, f, indent=2)

        yield f"data: {json.dumps({'stage': 'complete', 'current': num_pages, 'total': num_pages, 'message': 'All pages complete!', 'result': results})}\n\n"

    return Response(generate_pages_with_progress(), mimetype='text/event-stream')


@app.route('/api/coloring/regenerate', methods=['POST'])
def api_coloring_regenerate():
    """Regenerate a single coloring page with optional feedback and additional references."""
    try:
        from agents.coloring_page_generator import ColoringPageGenerator, PageConfig
        from agents.coloring_qa_checker import ColoringQAChecker

        data = request.json
        book_id = data.get("book_id")
        page_num = data.get("page_num", 1)
        feedback = data.get("feedback", "")  # User feedback for regeneration
        use_current_as_reference = data.get("use_current_as_reference", False)
        additional_references = data.get("additional_references", [])  # Extra reference image paths
        draft_mode = data.get("draft_mode", False)  # Use cheaper models for testing

        if not book_id:
            return jsonify({"ok": False, "error": "No book_id provided"}), 400

        book_dir = OUTPUT_DIR / book_id
        brief_path = book_dir / "coloring_brief.json"
        ref_path = book_dir / "reference_sheet.png"
        concepts_path = book_dir / "page_concepts.json"
        pages_dir = book_dir / "pages"
        current_page_path = pages_dir / f"page_{page_num:02d}.png"

        if not ref_path.exists():
            return jsonify({"ok": False, "error": "Reference sheet not found"}), 400

        with open(brief_path) as f:
            brief_data = json.load(f)

        concepts = []
        if concepts_path.exists():
            with open(concepts_path) as f:
                concepts = json.load(f)

        theme = brief_data.get('theme', 'General')
        age_level = brief_data.get('ageLevel', 'adult')
        difficulty = brief_data.get('difficulty', 'medium')
        style = brief_data.get('style', 'bold-easy')
        notes = brief_data.get('notes', '')
        concept = concepts[page_num - 1] if page_num <= len(concepts) else f"{theme} design {page_num}"

        # Add feedback to concept/notes if provided
        if feedback:
            concept = f"{concept}\n\n=== USER FEEDBACK FOR REGENERATION ===\n{feedback}\n=== END FEEDBACK ==="

        # Get previous subjects from other pages for uniqueness
        previous_subjects = []
        for idx, c in enumerate(concepts):
            if idx != page_num - 1:  # Exclude current page
                # Extract subject from concept
                skip_words = {'a', 'an', 'the', 'large', 'small', 'big', 'tiny', 'cute'}
                words = c.lower().split()
                for word in words:
                    clean_word = ''.join(ch for ch in word if ch.isalnum())
                    if clean_word and clean_word not in skip_words and len(clean_word) > 2:
                        previous_subjects.append(clean_word)
                        break

        config = PageConfig(
            page_num=page_num,
            concept=concept,
            theme=theme,
            age_level=age_level,
            difficulty=difficulty,
            style=style,
            notes=notes,
            previous_subjects=previous_subjects
        )

        output_path = pages_dir / f"page_{page_num:02d}.png"

        # Build list of reference images
        # Primary reference: current page or reference sheet
        primary_ref = current_page_path if use_current_as_reference and current_page_path.exists() else ref_path

        # Convert additional reference URLs to local paths
        extra_refs = []
        for ref_url in additional_references:
            # URLs like /api/files/ColoringBook/Title-123/pages/page_01.png
            if ref_url.startswith('/api/files/'):
                rel_path = ref_url.replace('/api/files/', '')
                local_path = OUTPUT_DIR / rel_path
                if local_path.exists():
                    extra_refs.append(local_path)
                    log.info(f"Added additional reference: {local_path}")

        # Combine draft_mode from request with global debug_mode
        effective_draft_mode = draft_mode or get_debug_mode()
        generator = ColoringPageGenerator(draft_mode=effective_draft_mode)
        qa_checker = ColoringQAChecker()

        # Generate with additional references if provided
        success, path = generator.generate_page(
            config,
            primary_ref,
            output_path,
            additional_references=extra_refs
        )

        if success:
            # Run QA but don't fail regeneration on QA failure
            # User explicitly requested this regeneration, so trust their judgment
            try:
                qa_result = qa_checker.check_page(path, age_level, difficulty, theme)
                qa_passed = qa_result.passed
                qa_scores = qa_result.scores
            except Exception as qa_error:
                log.warning(f"QA check failed: {qa_error}")
                qa_passed = None
                qa_scores = {}

            return jsonify({
                "ok": True,
                "page_num": page_num,
                "image_path": f"pages/page_{page_num:02d}.png",
                "qa_passed": qa_passed,
                "qa_scores": qa_scores
            })
        else:
            return jsonify({"ok": False, "error": "Image generation failed - API error"}), 500

    except Exception as e:
        log.exception("Page regeneration failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/coloring/cover', methods=['POST'])
def api_coloring_cover():
    """Generate cover and back cover for coloring book."""
    try:
        from agents.coloring_cover_generator import ColoringCoverGenerator, CoverBrief

        data = request.json
        book_id = data.get("book_id")
        feedback = data.get("feedback", "")  # User feedback for regeneration
        cover_type = data.get("cover_type", "")  # 'front', 'back', or '' for both
        draft_mode = data.get("draft_mode", False)  # Use cheaper models for testing
        if not book_id:
            return jsonify({"ok": False, "error": "No book_id provided"}), 400

        book_dir = OUTPUT_DIR / book_id
        brief_path = book_dir / "coloring_brief.json"
        pages_dir = book_dir / "pages"

        if not brief_path.exists():
            return jsonify({"ok": False, "error": "Brief not found"}), 400

        # Check that reference sheet was approved before generating covers
        approval_marker = book_dir / ".reference_approved"
        if not approval_marker.exists():
            return jsonify({
                "ok": False,
                "error": "Reference sheet not approved. Please approve the style sheet before generating covers."
            }), 403

        with open(brief_path) as f:
            brief_data = json.load(f)

        cfg = load_config()

        # Combine notes with feedback if provided
        notes = brief_data.get('notes', '')
        if feedback:
            notes = f"{notes}\n\n=== USER FEEDBACK FOR REGENERATION ===\n{feedback}\n=== END FEEDBACK ===" if notes else f"=== USER FEEDBACK FOR REGENERATION ===\n{feedback}\n=== END FEEDBACK ==="

        cover_brief = CoverBrief(
            title=brief_data.get('title', 'Coloring Book'),
            theme=brief_data.get('theme', 'General'),
            age_level=brief_data.get('ageLevel', 'adult'),
            difficulty=brief_data.get('difficulty', 'medium'),
            subtitle=brief_data.get('subtitle', ''),
            author=cfg.get('defaults', {}).get('author_name', 'Creative Studio'),
            notes=notes,
            style=brief_data.get('style', 'bold-easy')
        )

        # Get sample pages for reference
        sample_pages = []
        if pages_dir.exists():
            page_files = sorted(pages_dir.glob("page_*.png"))[:3]
            sample_pages = [Path(p) for p in page_files]

        # Combine draft_mode from request with global debug_mode
        effective_draft_mode = draft_mode or get_debug_mode()
        generator = ColoringCoverGenerator(draft_mode=effective_draft_mode)
        results = generator.generate_both(cover_brief, sample_pages, book_dir)

        response = {
            "ok": True,
            "book_id": book_id,
            "cover": None,
            "back_cover": None
        }

        if results['cover'][0]:
            response['cover'] = f"{book_id}/cover.png"
        if results['back_cover'][0]:
            response['back_cover'] = f"{book_id}/back_cover.png"

        return jsonify(response)

    except Exception as e:
        log.exception("Cover generation failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/coloring/pdf', methods=['POST'])
def api_coloring_pdf():
    """Build KDP-ready PDF for coloring book."""
    try:
        from agents.coloring_pdf_builder import ColoringPDFBuilder, ColoringBookPackage

        data = request.json
        book_id = data.get("book_id")
        if not book_id:
            return jsonify({"ok": False, "error": "No book_id provided"}), 400

        book_dir = OUTPUT_DIR / book_id
        brief_path = book_dir / "coloring_brief.json"
        pages_dir = book_dir / "pages"
        cover_path = book_dir / "cover.png"
        back_cover_path = book_dir / "back_cover.png"

        if not brief_path.exists():
            return jsonify({"ok": False, "error": "Brief not found"}), 400
        if not pages_dir.exists() or not list(pages_dir.glob("page_*.png")):
            return jsonify({"ok": False, "error": "No pages found. Generate pages first."}), 400

        with open(brief_path) as f:
            brief_data = json.load(f)

        cfg = load_config()
        trim_size = brief_data.get('bookSize', '8.5x8.5')

        package = ColoringBookPackage(
            title=brief_data.get('title', 'Coloring Book'),
            author=cfg.get('defaults', {}).get('author_name', 'Creative Studio'),
            theme=brief_data.get('theme', 'General'),
            age_level=brief_data.get('ageLevel', 'adult'),
            num_pages=brief_data.get('numPages', 24),
            trim_size=trim_size
        )

        builder = ColoringPDFBuilder(trim_size=trim_size)
        results = builder.build_all(
            package,
            str(pages_dir),
            str(cover_path),
            str(back_cover_path),
            str(book_dir)
        )

        return jsonify({
            "ok": True,
            "book_id": book_id,
            "result": results
        })

    except Exception as e:
        log.exception("PDF build failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/coloring/publish', methods=['POST'])
def api_coloring_publish():
    """Publish coloring book to KDP."""
    try:
        from agents.kdp_publisher import KDPPublisher, BookPackage, BookListing

        data = request.json
        book_id = data.get("book_id")
        dry_run = data.get("dry_run", False)

        if not book_id:
            return jsonify({"ok": False, "error": "No book_id provided"}), 400

        book_dir = OUTPUT_DIR / book_id
        brief_path = book_dir / "coloring_brief.json"
        interior_pdf = book_dir / "Interior.pdf"
        cover_pdf = book_dir / "Cover.pdf"
        kindle_cover = book_dir / "Kindle_Cover.jpg"

        missing = []
        if not brief_path.exists():
            missing.append("coloring_brief.json")
        if not interior_pdf.exists():
            missing.append("Interior.pdf")
        if not cover_pdf.exists():
            missing.append("Cover.pdf")
        if not kindle_cover.exists():
            missing.append("Kindle_Cover.jpg")

        if missing:
            return jsonify({"ok": False, "error": f"Missing files: {', '.join(missing)}. Build PDFs first."}), 400

        with open(brief_path) as f:
            brief_data = json.load(f)

        cfg = load_config()

        # Build listing for coloring book
        book_listing = BookListing(
            title=brief_data.get('title', 'Coloring Book'),
            subtitle=brief_data.get('subtitle', ''),
            author=cfg.get('defaults', {}).get('author_name', 'Creative Studio'),
            description=f"A {brief_data.get('difficulty', 'medium')} difficulty coloring book featuring {brief_data.get('theme', 'beautiful designs')}. Perfect for {brief_data.get('ageLevel', 'adult')} colorists.",
            categories=['Books > Arts & Photography > Graphic Design > Techniques > Use of Color'],
            keywords=[
                brief_data.get('theme', 'coloring'),
                'coloring book',
                f"{brief_data.get('ageLevel', 'adult')} coloring",
                brief_data.get('difficulty', 'medium'),
                'relaxation',
                'stress relief',
                'art therapy'
            ][:7],
            ai_disclosure_text="Entire work, with extensive editing",
            ai_tool_text="Claude",
            ai_disclosure_images="Many AI-generated images, with extensive editing",
            ai_tool_images="ChatGPT",
            ai_disclosure_translation="None"
        )

        book_package = BookPackage(
            listing=book_listing,
            interior_pdf_path=str(interior_pdf),
            cover_pdf_path=str(cover_pdf),
            cover_jpg_path=str(kindle_cover),
            us_price=cfg.get('defaults', {}).get('us_price', 9.99),
            is_kdp_select=True,
            dry_run=dry_run
        )

        log.info(f"Starting KDP publish for coloring book: {book_listing.title}")
        use_chrome = cfg.get('kdp', {}).get('use_chrome_profile', False)
        chrome_profile_name = cfg.get('kdp', {}).get('chrome_profile_name', 'Profile 2')

        try:
            with KDPPublisher(use_chrome_profile=use_chrome, chrome_profile_name=chrome_profile_name) as publisher:
                result = publisher.publish_book(book_package)
            return jsonify({"ok": True, "book_id": book_id, "result": result})
        except Exception as browser_error:
            error_msg = str(browser_error)
            if "ProcessSingleton" in error_msg or "profile directory" in error_msg:
                return jsonify({
                    "ok": False,
                    "error": "Chrome is currently running. Please close ALL Chrome windows and try again."
                }), 400
            raise

    except Exception as e:
        log.exception("Coloring book publish failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/files/<path:filepath>')
def api_files(filepath):
    """Serve generated files (images, PDFs)."""
    full_path = OUTPUT_DIR / filepath
    if full_path.exists() and full_path.is_file():
        return send_file(full_path)
    return jsonify({"error": "File not found"}), 404


@app.route('/api/books')
def api_books():
    """List all generated books."""
    books = []
    if OUTPUT_DIR.exists():
        for d in sorted(OUTPUT_DIR.iterdir(), reverse=True):  # Newest first
            if d.is_dir() and not d.name.startswith('.'):
                # Check if it has a story_package.json (indicates it's a book)
                story_path = d / "story_package.json"
                if story_path.exists():
                    info = {"id": d.name, "path": str(d)}
                    with open(story_path) as f:
                        pkg = json.load(f)
                    info["title"] = pkg.get("title") or pkg.get("story", {}).get("title", "Untitled")
                    books.append(info)
    return jsonify({"books": books})


# ─── Launch ───
def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://localhost:5555")


if __name__ == '__main__':
    print("\n  ╔══════════════════════════════════════╗")
    print("  ║       Book Factory Studio v1.0       ║")
    print("  ║   http://localhost:5555               ║")
    print("  ╚══════════════════════════════════════╝\n")

    threading.Thread(target=open_browser, daemon=True).start()
    host = os.environ.get('BOOKFACTORY_HOST', '127.0.0.1')
    app.run(host=host, port=5555, debug=False)
