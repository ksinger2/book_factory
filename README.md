# Book Factory — Quick Start

## Setup with Docker (recommended)

```bash
cp .env.example .env
# Edit .env with your API keys and Cloudflare tunnel token
docker compose up -d
```

That's it. The dashboard auto-starts on boot and is available at:
- **Local:** http://localhost:5555
- **External:** https://bookfactory.backtoirl.com (via Cloudflare tunnel)

Useful commands:
```bash
docker compose logs -f       # Watch logs
docker compose down           # Stop everything
docker compose up -d --build  # Rebuild after code changes
```

## Setup without Docker (manual)

```bash
cd ~/Desktop/book-factory
pip3 install -r requirements.txt
playwright install chromium
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
python run.py
```

## Open the Dashboard

Walk through each step: Setup → Research → Brief → Style → Export → Generate.

- **Local:** http://localhost:5555
- **External (tunnel):** https://bookfactory.backtoirl.com

## CLI Commands
| Command | What it does |
|---------|-------------|
| `python3 studio.py` | Full pipeline (research → story → art → PDF → publish) |
| `python3 studio.py --batch 5` | Make 5 books from top niches |
| `python3 studio.py --research-only` | Just find profitable niches |
| `python3 studio.py --from-brief brief.json` | Skip research, use your brief |
| `python3 studio.py --no-publish` | Everything except KDP upload |

## Custom Brief
Save as `brief.json`, then run `python3 studio.py --from-brief brief.json`:
```json
{
  "category": "Children's Fox Books",
  "age_range": "3-6",
  "animal": "fox",
  "theme": "forest adventure",
  "lesson": "bravery",
  "art_style": "Soft gouache/watercolor...",
  "formats": ["paperback", "ebook"],
  "trim_size": "8.5x8.5"
}
```

## Cost
~$1.30 per book (15 images + story generation). KDP is free.

## Art Style
Edit `config/studio_config.yaml` → `art.style` or pass via brief. Four presets available in the dashboard (Gouache, Digital, Colored Pencil, Flat Vector) or write your own.
