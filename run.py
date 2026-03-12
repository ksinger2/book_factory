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


@app.route('/api/research', methods=['POST'])
def api_research():
    """Run niche research."""
    try:
        from agents.niche_researcher import NicheResearcher

        data = request.json or {}
        use_fallback = data.get("use_fallback", True)

        researcher = NicheResearcher(use_fallback=use_fallback)
        results = researcher.run()

        # Save results
        report_path = OUTPUT_DIR / "niche_report.json"
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        return jsonify({"ok": True, "niches": results, "saved_to": str(report_path)})
    except Exception as e:
        log.exception("Research failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/story', methods=['POST'])
def api_story():
    """Generate a story from a brief."""
    try:
        from agents.story_engine import StoryEngine

        brief = request.json
        if not brief:
            return jsonify({"ok": False, "error": "No brief provided"}), 400

        engine = StoryEngine()
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
        book_id = f"{safe_title}-{timestamp}"
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

    # Build prompts with style, character, and restrictions
    def build_prompt(base_prompt):
        prompt = base_prompt
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
        "reference_image": reference_image
    }

    art_dir = book_dir / "art"
    art_dir.mkdir(exist_ok=True)

    def generate_with_progress():
        from agents.art_pipeline import ArtPipeline
        import time

        total_images = 2 + len(art_package['spreads'])  # char sheet + cover + spreads + back
        current = 0

        try:
            # Initialize pipeline with art style, eye style, and reference image from the brief
            art_style_for_pipeline = art_package.get('art_style', '')
            eye_style_for_pipeline = art_package.get('eye_style', '')
            reference_image_for_pipeline = art_package.get('reference_image', '')
            pipeline = ArtPipeline(
                style=art_style_for_pipeline,
                eye_style=eye_style_for_pipeline,
                reference_image=reference_image_for_pipeline
            )
            results = {
                "success": False,
                "character_sheet": None,
                "cover": None,
                "spreads": [],
                "back_cover": None,
                "failed_images": []
            }

            # Character sheet
            current += 1
            yield f"data: {json.dumps({'stage': 'character_sheet', 'current': current, 'total': total_images, 'message': 'Generating character sheet...'})}\n\n"

            char_sheet_path = art_dir / "character_sheets" / f"{art_package['character_name']}_sheet.png"
            char_sheet_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                _, char_path = pipeline.generate_character_sheet(
                    art_package["character_description"],
                    char_sheet_path,
                    style=art_style_for_pipeline
                )
                results["character_sheet"] = str(char_path)
                yield f"data: {json.dumps({'stage': 'character_sheet_done', 'current': current, 'total': total_images, 'message': 'Character sheet complete!', 'image_path': f'character_sheets/{art_package[\"character_name\"]}_sheet.png'})}\n\n"
            except Exception as e:
                results["failed_images"].append(f"character_sheet: {str(e)}")
                yield f"data: {json.dumps({'stage': 'character_sheet_error', 'current': current, 'total': total_images, 'message': f'Character sheet failed: {str(e)}'})}\n\n"
                char_path = None

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
    """Regenerate a single image."""
    try:
        from agents.art_pipeline import ArtPipeline

        data = request.json
        book_id = data.get("book_id")
        image_type = data.get("image_type")  # 'spread', 'cover', 'character_sheet'
        scene_index = data.get("scene_index", 1)  # 1-based

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

        # Initialize pipeline
        pipeline = ArtPipeline(style=art_style)

        if image_type == 'spread':
            if scene_index < 1 or scene_index > len(scenes):
                return jsonify({"ok": False, "error": "Invalid scene index"}), 400

            scene = scenes[scene_index - 1]  # Convert to 0-based
            scene_desc = scene.get('illustration_prompt', '')
            output_path = art_dir / f"scene_{scene_index:02d}.png"

            # Use fix_image method
            success, result = pipeline.fix_image(
                f"scene_{scene_index:02d}.png",
                char_sheet_path,
                scene_desc,
                illustration_type="spread",
                output_dir=book_dir,
                style=art_style
            )

            if success:
                return jsonify({
                    "ok": True,
                    "message": f"Scene {scene_index} regenerated",
                    "image_path": f"scene_{scene_index:02d}.png"
                })
            else:
                return jsonify({"ok": False, "error": result}), 500

        elif image_type == 'cover':
            cover_scene = scenes[0].get('illustration_prompt', '') if scenes else ''
            output_path = art_dir / "cover.png"

            _, _ = pipeline.generate_illustration(
                cover_scene,
                char_sheet_path,
                illustration_type="cover",
                output_path=output_path,
                style=art_style
            )

            return jsonify({
                "ok": True,
                "message": "Cover regenerated",
                "image_path": "cover.png"
            })

        elif image_type == 'character_sheet':
            char_desc = character.get('sheet_prompt', character.get('description', ''))
            output_path = char_sheet_path

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
        chrome_profile_name = cfg.get('kdp', {}).get('chrome_profile_name', 'Profile 2')
        try:
            with KDPPublisher(use_chrome_profile=True, chrome_profile_name=chrome_profile_name) as publisher:
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
    app.run(host='127.0.0.1', port=5555, debug=False)
