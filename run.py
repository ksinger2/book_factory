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

        # Save to output dir
        book_id = f"book-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
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


@app.route('/api/art', methods=['POST'])
def api_art():
    """Generate illustrations. Returns SSE stream for progress."""
    data = request.json
    book_id = data.get("book_id")
    if not book_id:
        return jsonify({"ok": False, "error": "No book_id provided"}), 400

    book_dir = OUTPUT_DIR / book_id
    story_path = book_dir / "story_package.json"

    if not story_path.exists():
        return jsonify({"ok": False, "error": "Story package not found. Generate story first."}), 400

    with open(story_path) as f:
        story_package = json.load(f)

    def generate():
        try:
            from agents.art_pipeline import ArtPipeline

            pipeline = ArtPipeline()
            art_dir = book_dir / "art"
            art_dir.mkdir(exist_ok=True)

            yield f"data: {json.dumps({'stage': 'starting', 'message': 'Initializing art pipeline...'})}\n\n"

            result = pipeline.generate_all(story_package, output_dir=art_dir)

            yield f"data: {json.dumps({'stage': 'complete', 'result': result})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'stage': 'error', 'error': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/pdf', methods=['POST'])
def api_pdf():
    """Build PDFs from story + art."""
    try:
        from agents.pdf_builder import PDFBuilder

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
            story = json.load(f)

        cfg = load_config()
        builder = PDFBuilder()
        result = builder.build_all(story, str(art_dir), str(book_dir))

        return jsonify({"ok": True, "book_id": book_id, "result": result})
    except Exception as e:
        log.exception("PDF build failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/publish', methods=['POST'])
def api_publish():
    """Publish to KDP using Chrome profile."""
    try:
        from agents.kdp_publisher import KDPPublisher

        data = request.json
        book_id = data.get("book_id")
        if not book_id:
            return jsonify({"ok": False, "error": "No book_id"}), 400

        book_dir = OUTPUT_DIR / book_id

        publisher = KDPPublisher(use_chrome_profile=True)
        # Build BookPackage from files in book_dir
        # This is the integration point — needs story + PDFs
        result = {"status": "ready", "message": "Close Chrome, then click Publish to launch KDP automation."}

        return jsonify({"ok": True, "result": result})
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
        for d in sorted(OUTPUT_DIR.iterdir()):
            if d.is_dir() and d.name.startswith("book-"):
                info = {"id": d.name, "path": str(d)}
                story_path = d / "story_package.json"
                if story_path.exists():
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
