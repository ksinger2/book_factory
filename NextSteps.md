# Book Factory - Session Context & Next Steps

> **Last Updated:** 2026-03-13 01:25
> **Session ID:** session-20260313a

---

## Latest Changes (This Session)

### Draft Mode Toggle (2026-03-13) - COST SAVINGS
Added UI toggle for draft mode to dramatically reduce testing costs:

#### Features
- **Toggle switch** on coloring book brief page (Cost Mode card)
- **Draft mode:** Uses dall-e-2 (~$0.02/image) - ~$0.50/book
- **Production mode:** Uses gpt-image-1 (~$0.05/image) - ~$2.50/book

#### Files Modified
- `agents/coloring_style_generator.py` - Added `draft_mode` parameter, uses dall-e-2 in draft mode
- `agents/coloring_page_generator.py` - Added `draft_mode` parameter, uses dall-e-2 with standard quality
- `agents/coloring_cover_generator.py` - Added `draft_mode` parameter
- `run.py` - All coloring endpoints now accept and pass `draft_mode`
- `dashboard.html` - Toggle UI, CSS for switch, passes `draft_mode` to all coloring API calls

#### API Endpoints Updated
- `/api/coloring/reference` - accepts draft_mode
- `/api/coloring/pages` - accepts draft_mode
- `/api/coloring/regenerate` - accepts draft_mode
- `/api/coloring/cover` - accepts draft_mode

---

### Previous: Cost Optimization (2026-03-12 Evening) - MAJOR
Reduced image generation costs by 75-85% (~$20/day → $3-5/day):

#### Retry Bug Fixes
- **Fixed off-by-one bug** in `art_pipeline.py` lines 464, 631, 945 - was running 4 retries instead of 3
- Changed `while attempt <= max_retries` → `while attempt < max_retries`

#### Fail-Fast Logic
- Added `CriticalImageFailure` exception class
- If character sheet fails after 3 retries, pipeline aborts immediately (saves money on subsequent images)

#### Quality & Model Changes
- Image quality: `high` → `medium` (50% cost reduction)
- Vision model: `gpt-4o` → `gpt-4o-mini` for QA checks (30x cheaper)
- Story model: Reverted to `gpt-4o` (gpt-4o-mini too restrictive for diverse content)
- Added `qa_first_only=True` flag - only QA character sheet, skip cover/spreads/back_cover

#### Files Modified
- `agents/art_pipeline.py` - Retry fixes, CriticalImageFailure, qa_first_only, vision model
- `agents/coloring_page_generator.py` - Quality setting
- `agents/coloring_style_generator.py` - Quality setting
- `agents/coloring_cover_generator.py` - Quality setting
- `agents/coloring_qa_checker.py` - Default model to gpt-4o-mini
- `agents/story_engine.py` - Model selection, diversity theme support
- `config/studio_config.yaml` - Quality: medium

### Diversity Content Support (2026-03-12 Evening)
- Added explicit support for LGBTQ+, cultural, and social themes in story prompts
- References published examples (And Tango Makes Three, Heather Has Two Mommies)
- Prevents overly cautious content filter rejections for legitimate children's book topics

### External Testing Setup (2026-03-12 Evening)
- Installed `cloudflared` for Cloudflare Tunnel
- Created tunnel: `bookfactory` → `bookfactory.backtoirl.com`
- Config at `~/.cloudflared/config.yml`
- **To start tunnel:** `cloudflared tunnel run bookfactory`
- **Access protection:** Set up via Cloudflare Access dashboard (one.dash.cloudflare.com)

### OpenAI Image Generation Skill (2026-03-12 Evening)
Created `~/.claude/skills/openai-image-generation/` with:
- Cost optimization guidelines (70-90% savings possible)
- Prompt templates for game assets and illustrations
- Sprite sheet generation patterns
- Book Factory specific patterns in `references/book-factory-patterns.md`

### Previous: Environment Setup (2026-03-12 PM)
- Created Python virtual environment (`venv/`) for dependency isolation
- Installed all requirements via `pip install -r requirements.txt`
- Flask dashboard server verified running on **http://localhost:5555**

### Test Run: Baroque Blooms Coloring Book (2026-03-12)
- Successfully generated a 12-page coloring book with reference sheet
- Output in `output/Baroque_Blooms-20260312_082203/`
- All pipeline fixes (theme, uniqueness, edge cutoff) applied in this run

### Coloring Book Pipeline Fixes (2026-03-12)
Critical fixes for theme handling, page uniqueness, and edge cutoff issues:

#### Fix 1: Theme Flow (CRITICAL)
**Problem:** User selected "insects" but got dragons/unicorns - custom theme saved as empty string
**Solution:**
- Added `oninput` handler to custom theme input to preserve value during re-renders
- `updateColoringTheme()` now preserves custom value before re-render
- Added validation in `saveColoringBrief()` - alerts if theme empty
- Server-side validation in `/api/coloring/brief` returns 400 if theme missing
- Added fallback: `theme = brief_data.get('theme', '').strip() or 'General'`
- Added new THEME_GUIDELINES: `insects`, `bugs`, `birds`

#### Fix 2: Page Uniqueness (HIGH)
**Problem:** Same creature in same pose on multiple pages - no cross-page context
**Solution:**
- Enhanced `_generate_concepts_with_llm()` with exclusion_list parameter
- Added `_extract_subject()` helper to identify primary subject
- Added `_validate_unique_subjects()` to verify 80%+ uniqueness
- Added `previous_subjects: List[str]` field to `PageConfig` dataclass
- Updated page prompt with `*** UNIQUENESS - DO NOT REPEAT ***` section
- `run.py` now tracks `generated_subjects` list during generation loop
- Each page receives all previously generated subjects to avoid repetition

#### Fix 3: Edge Cutoff Prevention (HIGH)
**Problem:** Creatures cropped at page edges but QA passes - prompts too weak, scoring too lenient
**Solution:**
- Restructured page prompt with `*** CRITICAL - SAFE ZONE FRAMING - READ FIRST ***`
- 10% margin rule: NOTHING enters outer 10% zone
- Added explicit failure examples (dragon tail, unicorn horn, butterfly antenna)
- Composition check with ✓ checkboxes before drawing
- Subject size constraint: 50-70% of safe zone
- QA scorer: `NO_EDGE_CUTOFF` now BINARY PASS/FAIL (0-20 for any cut, 80-100 for pass)
- Stricter validation: edge cutoff requires score ≥50 (was 70)

### Files Modified
- `dashboard.html` - oninput handler, theme preservation, validation
- `run.py` - Theme validation, subject tracking in generation loop
- `agents/coloring_style_generator.py` - Theme guidelines, LLM concept generation with exclusions
- `agents/coloring_page_generator.py` - Safe zone prompt, previous_subjects field
- `agents/coloring_qa_checker.py` - Stricter edge cutoff scoring

### Previous Session Changes
- Full Pipeline Working - Reference sheet → Page generation → Cover → PDF build
- Theme-Dominant Prompting - Style generator emphasizes theme
- QA Checker Bug Fixed - `NO_EDGE_CUTOFF` was missing from `score_keys`
- Progress Bar Optimization - Targeted DOM updates
- Character Sheet Guidance - Text + reference image for regeneration
- Output Directory Organization - `ChildrensBook/` and `ColoringBook/` subdirs

---

## Agent Status Reports

### Coloring Book Agents (UPDATED)
**Domain:** Coloring book generation pipeline
**Status:** READY - Cost optimized with draft mode

**Components:**
- `coloring_style_generator.py` - Reference sheet + concept generation with uniqueness validation
- `coloring_page_generator.py` - Individual page generation with safe zone framing + previous subjects tracking
- `coloring_cover_generator.py` - Cover generation
- `coloring_qa_checker.py` - GPT-4o-mini vision-based quality validation with strict edge checking

**Recent Changes (2026-03-13):**
- **Draft Mode Toggle:** All generators accept `draft_mode` parameter for cheaper testing
- **Cost Savings:** Draft mode uses dall-e-2 (~$0.02/image vs ~$0.05/image)
- **UI Toggle:** Switch on brief page to toggle between draft/production modes

**Previous Changes (2026-03-12 PM):**
- **Theme Flow Fixed:** Custom theme now preserved during UI interactions, validated on save
- **Page Uniqueness:** LLM concepts now validated for 80%+ uniqueness, previous subjects passed to each page
- **Edge Cutoff Prevention:** Safe zone framing in prompts, binary pass/fail QA scoring
- Added THEME_GUIDELINES for: `insects`, `bugs`, `birds`
- `PageConfig` now includes `previous_subjects: List[str]` field

**Previous Changes (2026-03-12 AM):**
- Fixed QA checker: `NO_EDGE_CUTOFF` now properly parsed from responses
- Rewrote style generator prompt to put theme FIRST with strong emphasis
- Added art style support throughout pipeline (zentangle, mandala, kawaii, etc.)

**Current State:**
- Generating coloring books with theme-appropriate content
- Page uniqueness enforced via subject tracking
- Edge cutoff strictly enforced with binary QA scoring
- 10 art styles available
- Age levels: kid, tween, teen, ya, adult, elder

**Next Steps:**
- Test end-to-end with "insects" theme to verify fixes
- Add style preview images in UI
- Consider batch generation for faster throughput

**Blockers/Notes:**
- Large page counts (24+) take significant time
- Edge cutoff may cause more QA retries initially (intentional - better quality)

---

### Niche Researcher
**Domain:** Market research, Amazon BSR analysis, keyword research
**Status:** READY (with caveats)

**Recent Changes:**
- Fixed critical infinite recursion bug in `_get_keyword_suggestions()` when Amazon API fails
- Now returns fallback-generated suggestions directly instead of recursive calls

**Current State:**
- Agent functional using fallback/mock data (live Amazon scraping likely blocked)
- `niche_report.json` contains 11 ranked niches: Dogs (#1), Bedtime (#2), Rhyming (#3)
- 16 brief.json files found in output/ - active book production

**Next Steps:**
- Fix competition score formula (currently always 0 due to high review counts in fallback data)
- Consider real data sources (Helium10, Jungle Scout API) for actual market data
- Improve character generation for abstract niches (bedtime, emotions → specific animals)

**Blockers/Notes:**
- Competition metric useless with current formula (all niches score 0)
- Recent books use custom briefs rather than auto-generated niche briefs

---

### Story Engine
**Domain:** Story generation, character creation, Amazon listing optimization
**Status:** READY

**Recent Changes (2026-03-12 Evening):**
- **Diversity content support:** Added explicit guidance for LGBTQ+, cultural, and social themes
- References published children's books as examples (And Tango Makes Three, etc.)
- Model: `gpt-4o` (gpt-4o-mini was too restrictive for diverse content)

**Previous Changes:**
- **Major API migration:** Claude → OpenAI GPT-4o
- Enhanced rate limit handling (max retries: 5, longer backoffs: 60-240s)
- Improved grammar enforcement with external `grammar_guide.txt`
- New `generate_character_from_story()` method for better character consistency
- User notes now highlighted as "CRITICAL USER REQUIREMENTS"

**Current State:**
- Fully functional with diversity theme support
- Grammar guide loaded from `resources/grammar_guide.txt`
- Outputs `story_package.json` (contains story, character, listing)

**Next Steps:**
- Update ARCHITECTURE.md to reflect Claude → OpenAI switch
- Test diverse themes end-to-end

**Blockers/Notes:**
- Cost estimate in ARCHITECTURE.md outdated (was for Claude, now uses GPT-4o)

---

### Art Pipeline
**Domain:** Illustration generation, character consistency, QA validation
**Status:** READY - Cost optimized

**Recent Changes (2026-03-12 Evening):**
- **Cost optimization:** 75-85% reduction in image generation costs
- Fixed retry bug (4 attempts → 3)
- Added `CriticalImageFailure` for fail-fast on first image failure
- Quality: `high` → `medium` (50% savings)
- Vision QA: `gpt-4o` → `gpt-4o-mini` (30x cheaper)
- Added `qa_first_only=True` - only QA character sheet, skip others

**Previous Changes:**
- **Character Sheet Guidance** - Users can provide text guidance + reference image
- **Model upgrade:** gpt-4o → gpt-image-1
- Added reference image support for character likeness from photos
- New "Character DNA" system for consistency across scenes

**Current State:**
- Cost-optimized pipeline (~$3-5/day vs $20/day)
- 9+ books with successful art_result.json completions
- Character sheet guidance working

**Next Steps:**
- Monitor cost reduction effectiveness
- Evaluate upgrading to gpt-image-1.5 for better consistency

**Blockers/Notes:**
- QA skipped on interior pages when `qa_first_only=True` (intentional for cost)

---

### PDF Builder
**Domain:** KDP-compliant PDF generation, cover creation, Kindle exports
**Status:** READY

**Recent Changes:**
- Standardized output filenames: `Interior.pdf`, `Cover.pdf`, `Kindle_Cover.jpg`
- Fixed ReportLab API: `setOpacity()` → `setFillAlpha()`
- Fixed image dimension calculation (removed erroneous `/inch` division)
- Fixed Kindle cover source (now uses actual `cover.png` from art/)

**Current State:**
- Working: Priscilla's book has all 3 files (Interior 22MB, Cover 56KB, Kindle 815KB)
- Christopher's book only has cover (older naming convention)

**Next Steps:**
- Commit current filename standardization changes
- Add PDF validation (page count, file size, structure)
- Add macOS font paths (current fallback is Linux-specific)

**Blockers/Notes:**
- Recent changes uncommitted
- Test PDF files in output directories could be cleaned up

---

### KDP Publisher
**Domain:** Amazon KDP automation, publishing workflow, pricing
**Status:** READY (untested)

**Recent Changes:**
- Added `chrome_profile_name` parameter for profile selection
- Updated Playwright launch args to pass profile directory
- Improved logging for profile launch

**Current State:**
- Full Playwright browser automation (769 lines)
- Supports paperback + eBook workflows
- AI disclosure fields implemented
- Dry-run mode available

**Next Steps:**
- **Run first real publish** (no publish_result.json files found = never tested end-to-end)
- Validate selectors against live KDP UI
- Add screenshot capture on failure for debugging

**Blockers/Notes:**
- **Never tested end-to-end:** Zero publish_result.json files exist
- Credentials not in config (good) - must be passed at runtime
- Chrome must be fully closed before automation runs
- Manual intervention required if MFA triggered

---

## Cross-Team Context

### Output Directory Structure (NEW)
```
output/
├── ChildrensBook/
│   └── {BookTitle}-{timestamp}/
│       ├── brief.json
│       ├── story_package.json
│       ├── art/
│       └── *.pdf
└── ColoringBook/
    └── {BookTitle}-{timestamp}/
        ├── coloring_brief.json
        ├── reference_sheet.png
        ├── page_concepts.json
        ├── pages/
        └── *.pdf
```

### Active Books in Pipeline

| Book ID | Type | Status | Stage | Next Action |
|---------|------|--------|-------|-------------|
| Priscillas_Magical_Forest_Adventure-20260307 | Children's | **COMPLETE** | PDF Done | Ready to publish |
| Christopher_and_the_Magical_Cars-20260308 | Children's | Art Done | Cover Only | Needs Interior.pdf |
| Baroque_Blooms-20260312 | Coloring | **COMPLETE** | 12 Pages Generated | Needs cover + PDF build |
| Holidays__Seasons_Coloring_Book-20260312 | Coloring | In Progress | Pages | Generating pages |

### Configuration State
- `config/studio_config.yaml` properly configured
- Chrome Profile 2 set for KDP automation
- **Art quality: medium** (changed from high for cost savings)
- **Vision QA: gpt-4o-mini** (changed from gpt-4o for cost savings)
- **QA: first image only** (qa_first_only=True)
- **Draft mode toggle:** Available in coloring book UI (dall-e-2 vs gpt-image-1)
- Retries: 3 (fixed off-by-one bug)
- Pricing: $9.99 paperback, $4.99 eBook

### External Access
- **URL:** https://bookfactory.backtoirl.com
- **Tunnel:** `cloudflared tunnel run bookfactory`
- **Auth:** Configure via Cloudflare Access dashboard

### Known Issues (Updated)
1. ~~**Art Pipeline QA broken**~~ - FIXED for coloring books
2. ~~**Theme ignored in coloring books**~~ - FIXED: Custom theme now validated and preserved
3. ~~**Duplicate pages in coloring books**~~ - FIXED: Subject uniqueness now enforced
4. ~~**Edge cutoff passes QA**~~ - FIXED: Strict binary pass/fail scoring
5. **Competition scores always 0** - Niche researcher formula issue
6. **ARCHITECTURE.md outdated** - still references Claude for story generation

### Uncommitted Changes
- `generate_coloring_book.py` - Standalone coloring book generation script
- `output/Baroque_Blooms-*` - Test coloring book outputs
- `venv/` - Python virtual environment (should stay untracked)

---

## Recommended Next Actions

Based on agent analysis, prioritized by impact:

1. **Build Baroque Blooms PDF** - 12 pages generated, needs cover + PDF assembly
2. **Publish Priscilla's book** - Ready for KDP, test the full publishing pipeline
3. **Generate Interior.pdf for Christopher** - Art complete, needs PDF build
4. **Test coloring book with "insects" theme** - Verify theme-specific fixes end-to-end
5. **Update ARCHITECTURE.md** - Add coloring book pipeline documentation

---

## Quick Links for Agents

| Agent | Primary Docs | Config |
|-------|--------------|--------|
| Niche Researcher | `ARCHITECTURE.md` | `config/studio_config.yaml` (research section) |
| Story Engine | `resources/grammar_guide.txt`, `ARCHITECTURE.md` | `config/studio_config.yaml` (defaults) |
| Art Pipeline | `prompting_skill.md`, `ARCHITECTURE.md` | `config/studio_config.yaml` (art section) |
| Coloring Agents | `resources/coloring_style_skill.md` | Brief settings in UI |
| PDF Builder | `ARCHITECTURE.md` | `config/studio_config.yaml` (defaults) |
| KDP Publisher | `ARCHITECTURE.md` | `config/studio_config.yaml` (kdp section) |
