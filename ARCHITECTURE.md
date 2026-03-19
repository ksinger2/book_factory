# Book Factory — Automated Children's Book Studio

## System Overview

Fully automated pipeline that researches profitable niches, generates children's picture books, and publishes them to Amazon KDP without human intervention.

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  RESEARCH    │───▶│  STORY       │───▶│  ART         │───▶│  PDF         │───▶│  KDP         │
│  AGENT       │    │  ENGINE      │    │  PIPELINE    │    │  BUILDER     │    │  PUBLISHER   │
│              │    │              │    │              │    │              │    │              │
│ • Niche scan │    │ • Plot gen   │    │ • Char sheet │    │ • Interior   │    │ • Form fill  │
│ • Keyword    │    │ • Rhyme/text │    │ • 14 spreads │    │ • Cover      │    │ • Upload     │
│   research   │    │ • Listing    │    │ • QA check   │    │ • Kindle JPG │    │ • Price      │
│ • Comp anal  │    │ • Metadata   │    │ • Eye fix    │    │              │    │ • Publish    │
└─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                                                                              │
       └──────────────── ORCHESTRATOR (studio.py) ────────────────────────────────────┘
```

## Module Details

### 1. Research Agent (`agents/niche_researcher.py`)
**Runs in parallel with production pipeline.**

What it does:
- Scrapes Amazon BSR (Best Seller Rank) data for children's book categories
- Analyzes competition density (# of reviews, age of top books)
- Identifies "blue ocean" niches: high demand + low competition
- Tracks keyword search volume via auto-suggest scraping
- Scores niches by profitability potential

Key insight for discoverability as a new author:
- Target LONG-TAIL categories (not "Children's Books" but "Children's Fox Books")
- Books with <50 reviews in top 10 = low competition
- BSR under 100k in subcategory = viable demand
- Series books cross-promote each other
- KDP Select (Kindle Unlimited) = discovery engine for unknowns

Output: `niche_report.json` with ranked opportunities

### 2. Story Engine (`agents/story_engine.py`)
Uses OpenAI GPT-4o (or GPT-4o-mini in debug mode) to generate complete story packages.

Input: niche brief (theme, age range, animal, lesson)
Output:
- story.json: 12 scenes with text + illustration prompts + composition notes
- listing.json: title, subtitle, description, 7 keywords, categories
- character.json: detailed character description for art consistency

Quality gates:
- Word count validation (300-500 words for ages 3-6)
- Rhyme scheme checker
- Reading level validation (Flesch-Kincaid)
- No problematic content

### 3. Art Pipeline (`agents/art_pipeline.py`)
Uses OpenAI gpt-image-1 for illustration generation.

Flow:
1. Generate character reference sheet
2. Generate 14 images (cover, 12 spreads, back cover) using char sheet as reference
3. **Automated QA** — vision model checks each image for:
   - Eye consistency (white highlights present)
   - Character match to reference sheet
   - Composition matches layout spec
   - No text/watermarks in image
4. Auto-regenerate any images that fail QA (up to 3 retries)

Lessons from Luna build:
- ALWAYS use character sheet as `images.edit()` reference
- Eye highlights must be explicitly demanded in every prompt
- Rate limit handling with exponential backoff
- Skip existing files for resume capability

### 4. PDF Builder (`agents/pdf_builder.py`)
Parameterized version of our working `build_kdp_files.py`.

Supports:
- Multiple trim sizes (8.5x8.5, 8x10, 6x9)
- Variable page counts (24-48)
- Dynamic text positioning from story.json
- Interior + wraparound cover + Kindle cover JPG

### 5. KDP Publisher (`agents/kdp_publisher.py`)
Playwright-based browser automation (NOT Chrome extension).

Why Playwright over Chrome extension:
- Runs headless (no GUI needed)
- Reliable selectors (CSS/XPath)
- File upload works programmatically
- No tab ID issues, no connection drops
- Can run on a server/cron job

Flow:
1. Login to KDP (stored credentials)
2. Create new paperback title
3. Fill details (title, author, description, categories, keywords)
4. Upload interior PDF + cover PDF
5. Set pricing ($9.99 paperback)
6. Publish paperback
7. Create Kindle eBook from same title
8. Upload interior PDF + cover JPG
9. Set pricing ($4.99 eBook, 70% royalty)
10. Publish eBook

### 6. Orchestrator (`studio.py`)
Main entry point. Config-driven, runs everything.

```
python3 studio.py                          # Full pipeline: research → generate → publish
python3 studio.py --research-only          # Just run niche research
python3 studio.py --from-brief brief.json  # Skip research, use provided brief
python3 studio.py --batch 5                # Generate 5 books from top 5 niches
python3 studio.py --no-publish             # Everything except KDP upload
```

## Configuration

All in `config/studio_config.yaml`:
```yaml
openai_api_key: "sk-..."
anthropic_api_key: "sk-..."  # for KDP marketing agent (Claude)
kdp_email: "..."
kdp_password: "..."

defaults:
  trim_size: "8.5x8.5"
  age_range: "3-6"
  price_paperback: 9.99
  price_ebook: 4.99
  author_name: "Starlit Stories Press"
  publisher: "Starlit Stories Press"

art:
  style: "Soft gouache/watercolor..."
  quality: "high"
  retries: 3
  qa_enabled: true

research:
  min_bsr: 100000        # Max BSR to consider viable
  max_competition: 50    # Max reviews in top 10
  categories:            # Focus areas
    - "Children's Animal Books"
    - "Children's Bedtime Stories"
    - "Children's Friendship Books"
```

## Discovery Strategy (How to Get Found as Unknown Author)

1. **Kindle Unlimited (KU)** — Enroll eBooks in KDP Select. KU readers browse and borrow freely = massive discovery. You earn per page read.

2. **Series strategy** — Each book links to the next. "Luna and the Starlit Trail" → "Luna and the Moonlit Pond" → etc. Amazon's algorithm promotes series.

3. **Long-tail keywords** — Don't compete on "children's book." Target "fox bedtime story for toddlers ages 3-5." Less competition, more targeted buyers.

4. **Category stacking** — Pick 2 specific categories where you can rank quickly. "Children's Fox Books" has way less competition than "Children's Fiction."

5. **Volume** — More books = more surface area for discovery. Each book is a lottery ticket. 10 books >> 1 book.

6. **A+ Content** — Amazon allows enhanced product pages with comparison tables linking your books.

7. **Price pulsing** — Launch at $0.99 for 3 days to get initial sales velocity, then raise to $4.99.

## Cost Estimate Per Book

| Component | Cost |
|-----------|------|
| OpenAI gpt-image-1 (15 images @ ~$0.08 each) | ~$1.20 |
| OpenAI GPT-4o (story generation) | ~$0.10 |
| Amazon KDP | Free (they take % of sale) |
| **Total per book** | **~$1.30** |

At $4.99 eBook (70% = $3.47 royalty) + $9.99 paperback ($1.79 royalty):
- Break even: 1 sale
- 10 books/day × 30 days = 300 books × even 1 sale each = $1,578/mo royalties

## Deployment

Docker Compose runs two services with auto-restart on boot:

```yaml
services:
  bookfactory:    # Flask app on port 5555
    build: .
    restart: unless-stopped

  tunnel:         # Cloudflare tunnel → bookfactory.backtoirl.com
    image: cloudflare/cloudflared:latest
    restart: unless-stopped
```

**Quick start:** `cp .env.example .env && docker compose up -d`

The `.env` file holds API keys and tunnel token (not committed — see `.env.example` for template).

`output/` and `config/` are bind-mounted so data persists outside the container.

## File Structure

```
book-factory/
├── studio.py                 # Main orchestrator
├── run.py                    # Flask web server (dashboard)
├── Dockerfile                # Python 3.11-slim container
├── docker-compose.yml        # bookfactory + cloudflare tunnel
├── .env.example              # Template for API keys & tunnel token
├── .dockerignore             # Exclude secrets/venv from Docker build
├── .gitignore                # Exclude secrets/venv/output from git
├── ARCHITECTURE.md           # This file
├── config/
│   └── studio_config.yaml    # All configuration
├── agents/
│   ├── niche_researcher.py   # Amazon niche analysis
│   ├── story_engine.py       # GPT-4o story generation
│   ├── art_pipeline.py       # OpenAI image generation + QA
│   ├── pdf_builder.py        # ReportLab PDF assembly
│   └── kdp_publisher.py      # Playwright KDP automation
├── templates/
│   ├── story_prompt.txt      # Story generation system prompt
│   ├── listing_prompt.txt    # Listing generation prompt
│   └── character_prompt.txt  # Character sheet prompt template
├── scripts/
│   └── run_on_mac.py         # Local Mac runner (art gen only)
└── output/
    └── {book-id}/            # Per-book output directory
        ├── story.json
        ├── listing.json
        ├── art/
        ├── Luna_KDP_Interior.pdf
        ├── Luna_KDP_Cover.pdf
        └── Luna_Kindle_Cover.jpg
```
