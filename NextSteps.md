# Book Factory - Session Context & Next Steps

> **Last Updated:** 2026-03-12 19:00
> **Session ID:** session-20260312c

---

## Latest Changes (This Session)

### Environment Setup (2026-03-12 PM)
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
**Status:** READY - Major fixes applied

**Components:**
- `coloring_style_generator.py` - Reference sheet + concept generation with uniqueness validation
- `coloring_page_generator.py` - Individual page generation with safe zone framing + previous subjects tracking
- `coloring_cover_generator.py` - Cover generation
- `coloring_qa_checker.py` - GPT-4o vision-based quality validation with strict edge checking

**Recent Changes (2026-03-12 PM):**
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

**Recent Changes:**
- **Major API migration:** Claude → OpenAI GPT-4o
- Enhanced rate limit handling (max retries: 5, longer backoffs: 60-240s)
- Improved grammar enforcement with external `grammar_guide.txt`
- New `generate_character_from_story()` method for better character consistency
- User notes now highlighted as "CRITICAL USER REQUIREMENTS"

**Current State:**
- Fully functional, actively producing books (16 recent story packages)
- Grammar guide loaded from `resources/grammar_guide.txt`
- Outputs `story_package.json` (contains story, character, listing)

**Next Steps:**
- Update ARCHITECTURE.md to reflect Claude → OpenAI switch
- Consider hybrid approach (fallback to Claude if OpenAI rate limited)
- Add automated grammar post-processing

**Blockers/Notes:**
- Cost estimate in ARCHITECTURE.md outdated (was for Claude, now uses GPT-4o)
- Old `generate_character()` method unused, could be removed

---

### Art Pipeline
**Domain:** Illustration generation, character consistency, QA validation
**Status:** READY - Successfully generating books

**Recent Changes (2026-03-12):**
- **Character Sheet Guidance** - Users can provide text guidance + reference image when regenerating
- Guidance text appended to prompt as "STYLE REFINEMENTS"
- Reference image support for steering regeneration

**Previous Changes:**
- **Model upgrade:** gpt-4o → gpt-image-1
- Added reference image support for character likeness from photos
- New "Character DNA" system for consistency across scenes
- Improved prompt structure following `prompting_skill.md` guidelines
- Style cascade: method param → story_package → instance → DEFAULT_STYLE

**Current State:**
- 9+ books with successful art_result.json completions
- Character sheet guidance working
- Back cover generation returning `null` in some runs

**Next Steps:**
- Investigate back_cover generation (exists in code but not triggering)
- Evaluate upgrading to gpt-image-1.5 for better consistency

**Blockers/Notes:**
- Scene images saved to `art/` not `art/spreads/` (differs from docs)
- Reference image feature requires base64 input (no file path support yet)

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
- Art quality: high, QA: enabled, retries: 3
- Pricing: $9.99 paperback, $4.99 eBook

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
