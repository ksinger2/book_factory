# Book Factory — Quick Start

## Setup (one time)
```bash
cd ~/Desktop/book-factory
pip3 install pyyaml requests beautifulsoup4 openai anthropic reportlab pillow playwright
playwright install chromium
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

## Open the Dashboard
```bash
open dashboard.html
```
Walk through each step: Setup → Research → Brief → Style → Export → Generate.

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
