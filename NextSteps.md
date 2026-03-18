# Book Factory - Session Context & Next Steps

> **Last Updated:** 2026-03-18
> **Session ID:** session-20260318a

---

## Latest Changes (2026-03-18)

### Bug Fixes — Story Generation (QA verified, live tested)

#### Fix 1: Listing JSON parse crash (root cause found)
**Problem:** `Failed to parse listing JSON: Expecting ',' delimiter` — listing prompt with 6 scene summaries was hitting the 2048 token cap and GPT was truncating the JSON mid-stream. No amount of repair logic can fix a truncated response.
**Solution:** Increased listing `max_tokens` from 2048 → 3072.

#### Fix 2: JSON repair fallback hardening
**Solution:** Added `json-repair` library as 4th-stage fallback in `_parse_json_response` (handles unescaped quotes in description strings). Added to `requirements.txt`.

#### Fix 3: Capitalization — standard English rules
**Problem:** Overcomplicated verse-line rules caused GPT to either capitalize every line OR make everything lowercase.
**Solution:** Replaced with plain standard English: sentence starts + proper nouns capitalized, everything else lowercase. Applied to both rhyming and prose system prompts and `grammar_guide.txt`.

**QA Results (2026-03-18):**
- 9/9 unit tests passing
- 23/24 E2E tests passing (1 UI scene-edit gap, unrelated to story generation)
- Live story generation test: `ok: true`, 12 scenes, listing parsed (1134 chars), capitalization correct

**Files Modified:**
- `agents/story_engine.py` — listing max_tokens 2048→3072, json-repair fallback, capitalization rules
- `resources/grammar_guide.txt` — simplified capitalization rules
- `requirements.txt` — added json-repair

---

## Previous Changes (2026-03-17)

### Debug/Cost-Saving Mode for Testing
Added global debug mode to reduce API costs by ~80% during development and testing:

**What it does:**
- **Story Engine:** Uses `gpt-4o-mini` instead of `gpt-4o` (~90% savings)
- **Art Pipeline:** Uses `dall-e-2` instead of `gpt-image-1` (~60% savings)
- **Image Size:** Uses `1024x1024` instead of `1536x1024` (faster)
- **Vision QA:** Skipped entirely (100% savings)
- **Reference Analysis:** Skipped (saves vision API calls)

**How to enable:**

Option 1 - Config file (`config/studio_config.yaml`):
```yaml
global:
  debug_mode: true  # Master switch for all agents
```

Option 2 - Environment variable:
```bash
BOOK_FACTORY_DEBUG=true python run.py
```

Option 3 - For E2E tests:
```bash
BOOK_FACTORY_DEBUG=true python3 tests/test_full_workflow.py --full
```

**Cost comparison per full book:**
| Component | Production | Debug Mode | Savings |
|-----------|-----------|------------|---------|
| Story Generation | gpt-4o (~$0.03) | gpt-4o-mini (~$0.003) | 90% |
| Images (each) | gpt-image-1 ($0.05) | dall-e-2 ($0.02) | 60% |
| Vision QA | gpt-4o-mini | skipped | 100% |
| **Total per test** | ~$3-5 | ~$0.50-1.00 | **80%** |

**Files modified:**
- `agents/story_engine.py` - Added `debug_mode` parameter
- `agents/art_pipeline.py` - Added `debug_mode` parameter, uses cheaper models
- `config/studio_config.yaml` - Added `global.debug_mode` master switch
- `run.py` - Added `get_debug_mode()` helper, wired to all agent constructors

---

## Previous Changes (2026-03-16)

### Image Regeneration Fixes
- **Character visual guide** now loaded from `art_result.json` when regenerating images
  - Fixes "NO character visual guide available" warning in logs
  - Ensures character DNA is preserved during regeneration
- **Moderation error handling** added to art pipeline
  - Catches OpenAI `BadRequestError` for moderation/safety/content_policy blocks
  - Sanitizes prompt automatically and retries (replaces trigger words)
  - New `_sanitize_prompt_for_moderation()` method handles false positives
  - Helpful error message shown in dashboard if all retries fail
- **Improved error messages** for moderation blocks in dashboard

### Debug Mode for Step-by-Step Image Approval
New configuration option to pause after each image and wait for user approval:
- **Config options** added to `studio_config.yaml`:
  - `art.debug_mode: true/false` - For children's book illustrations
  - `coloring.debug_mode: true/false` - For coloring book pages
- **New API endpoint** `/api/approve-image` to continue generation
- **Dashboard UI** shows approval panel when in debug mode:
  - Yellow-bordered panel with "Approve & Continue" and "Regenerate" buttons
  - Appears after each image (cover, spreads, or pages)
  - Pipeline pauses until user approves or regenerates
- Works for both **Children's Books** and **Coloring Books**

---

## Previous Changes (2026-03-15)

### Story Regeneration with Additive Prompt
- **Modal dialog** replaces confirm() when clicking "Regenerate Story"
- **Textarea** for additional guidance (e.g., "Make it funnier", "Add a wise owl character")
- **Guidance appended** to notes field with `=== ADDITIONAL GUIDANCE FOR REGENERATION ===` header
- **Click-outside-to-close** behavior for better UX
- **Tested** with 9 end-to-end Playwright tests (all passing)

---

## Previous Changes (2026-03-14)

### Coloring Book Marketing Tab
- **Marketing tab** added to Coloring Book Publish step
  - Same functionality as Children's Book marketing (keywords, categories, description, ads, social)
  - Uses existing `/api/marketing/analyze` endpoint with `ColoringBook/` prefix

### Removed Find Niche + Added KDP Marketing Agent
Major pipeline refactor:
- **Removed** Niche Researcher agent and "Find Niche" step (non-functional Amazon scraping)
- **Added** KDP Marketing Agent (`agents/kdp_marketing.py`) for post-publish optimization
- **Dashboard** now has 6 steps instead of 7 for Children's Book mode
- **Marketing tab** added to Output step with:
  - 7 optimized KDP keywords (copyable)
  - 2-3 category suggestions with reasoning
  - SEO-optimized HTML description
  - Amazon Ads campaign plan (keywords, bids, budget)
  - Social media posts for Instagram, Facebook, Pinterest, TikTok
  - Quick wins checklist for immediate actions

### Dashboard Branding
- Added **favicon** (open book icon) for browser tab
- Dashboard accessible via Cloudflare tunnel: https://bookfactory.backtoirl.com

### KDP Content Tab Automation
Based on manual KDP publish attempt for Priscilla's book, improved `_fill_content_tab_paperback()`:
- **ISBN Assignment** - Select "Get a free KDP ISBN" → Click "Assign ISBN"
- **Print Options** - Premium Color, 8.5x8.5 trim, No bleed, Glossy finish
- **Upload Flow** - Added `_wait_for_upload_complete()` for file processing

---

## Agent Status Summary

| Agent | Status | Recent Activity | Critical Issues |
|-------|--------|-----------------|-----------------|
| Story Engine | PRODUCTION-READY | 25+ books generated | Word count slightly tight (289 vs 300) |
| Art Pipeline | READY | 15 books with art | 3 recent books missing spreads in art_result.json |
| PDF Builder | READY | 9 complete PDFs | 2 books have 15KB interior PDFs (too small) |
| KDP Publisher | READY | Content tab automated | Selectors need live validation |
| KDP Marketing | NEW | Just created | Needs end-to-end testing |

**Books Ready for Publishing:**
- Priscilla's Magical Forest Adventure - **COMPLETE** (Interior 22MB, Cover 56KB, Kindle 815KB)
- Thomass New Friend - Complete
- Bianca the Cyborg Cows Space Adventure - Complete
- Carl and the Enchanted Forest - Complete
- Christopher and the Magical Cars - Complete

---

## Agent Status Reports

### KDP Marketing Agent
**Status:** NEW (2026-03-14)

**Current Capabilities:**
- Keyword analysis with search volume/competition estimation (7 keywords for KDP)
- Category suggestions with fit scoring and reasoning
- SEO-optimized book description with HTML formatting
- Title/subtitle optimization
- Amazon Ads campaign planning (keywords, match types, bids, budget)
- Social media content generation (Instagram, Facebook, Pinterest, TikTok)
- Quick wins checklist for immediate marketing actions
- Saves results to `marketing_result.json` in book directory

**API Endpoints:**
- `POST /api/marketing/analyze` - Full marketing analysis
- `POST /api/marketing/keywords` - Quick keyword-only analysis

**Dashboard Integration:**
- Marketing tab in Output step
- Copy buttons for keywords, description, social posts
- Quick wins checklist with checkboxes
- Regenerate button for re-running analysis

**Configuration:**
- Model: claude-sonnet-4-20250514
- Max retries: 3 with exponential backoff

**Next Steps:**
1. End-to-end testing with real published book
2. Validate keyword suggestions against Amazon search
3. Consider adding competitor analysis feature

---

### Story Engine
**Status:** PRODUCTION-READY

**Current Capabilities:**
- 12-scene children's stories (AABB rhyming or prose)
- Character creation from story text with diversity support
- Amazon listing generation with SEO optimization
- Quality validation (scene count, word count, rhyme patterns)
- **Cost-saving mode** uses gpt-4o-mini for testing (2026-03-17)

**Configuration:**
- Model: gpt-4o (or gpt-4o-mini in debug mode)
- Max retries: 5 with exponential backoff
- Grammar guide: resources/grammar_guide.txt
- **global.debug_mode: false** - Uses cheaper model when true

**Recent Activity:**
- 25+ story packages generated
- Latest: "The Adventures of Panda Pippin" (2026-03-13)
- Diversity content support active (LGBTQ+, cultural themes)

**Issues:**
- Word count validation slightly tight (289 vs 300 minimum in some stories)
- ARCHITECTURE.md still references Claude API (now uses OpenAI)

**Next Steps:**
1. Adjust word count minimum to 280-290 (more realistic for GPT-4o)
2. Update ARCHITECTURE.md documentation

---

### Art Pipeline
**Status:** READY - Cost optimized + Debug mode

**Current Capabilities:**
- Character sheet generation (4-panel reference)
- Scene illustration with reference-based consistency
- Character DNA extraction via GPT-4o vision
- Vision-based QA (gpt-4o-mini for cost savings)
- Recurring character detection
- **Moderation error handling** with automatic prompt sanitization
- **Debug mode** for step-by-step image approval
- **Cost-saving mode** uses dall-e-2 and skips QA (2026-03-17)

**Configuration:**
- Image model: gpt-image-1 (or dall-e-2 in debug mode)
- Image quality: medium (50% cost savings)
- QA: first image only (qa_first_only=True), skipped in debug mode
- Max retries: 3
- **global.debug_mode: false** - Master switch for cost-saving mode
- **art.debug_mode: false** - Step-by-step approval mode

**Recent Activity:**
- 15 books with art_result.json files
- Thomass New Friend: Complete (13 files, 38MB)
- Cost reduced 75-85% from previous settings
- 2026-03-16: Added moderation error handling and debug mode

**Issues:**
- 3 recent books have empty spreads arrays in art_result.json
- Eye highlight consistency sometimes requires retries
- Character sheet naming inconsistent (space before underscore in some)

**Resolved:**
- ~~Character visual guide not loaded during regeneration~~ (Fixed 2026-03-16)
- ~~Moderation false positives causing repeated failures~~ (Fixed 2026-03-16)

**Next Steps:**
1. Fix incomplete art_result.json files for Panda Pippin, Thomas variants
2. Consider qa_first_spread option for early drift detection

---

### PDF Builder
**Status:** READY

**Current Capabilities:**
- Interior PDF (4 trim sizes: 8.5x8.5, 8.5x11, 6x9, 5x8)
- Wraparound cover with dynamic spine calculation
- Kindle cover export (2560x3900 JPG)
- Full-bleed images with text overlays

**Configuration:**
- Trim: 8.5x8.5 inches
- Bleed: 0.125 inches
- Output: Interior.pdf, Cover.pdf, Kindle_Cover.jpg

**Recent Activity:**
- 9 complete PDF builds (Interior + Cover + Kindle)
- Priscilla's book: 22MB interior, ready for KDP

**Issues:**
- 2 books have 15KB interior PDFs (Carl, Christophers_Magical_Car_Journey)
  - Suggests PDFs built before art was available
- Font paths Linux-specific (macOS fallback degraded)

**Next Steps:**
1. Rebuild failed PDFs (15KB files)
2. Add validation to detect suspiciously small files
3. Add macOS font path support

---

### KDP Publisher
**Status:** READY (untested end-to-end)

**Current Capabilities:**
- Playwright browser automation
- Paperback + eBook publishing workflows
- AI disclosure field handling
- Metadata automation (title, description, keywords, categories)
- Pricing and KDP Select enrollment
- Dry-run mode for testing
- Chrome profile support for pre-authenticated sessions
- **Content tab automation** (ISBN, print options, cover finish)

**Configuration:**
- use_chrome_profile: false (currently disabled)
- chrome_profile_name: Profile 2
- Author: "Starlit Stories Press"
- Price: $9.99 paperback, $4.99 eBook

**Recent Activity:**
- 2026-03-14: Content tab automation improved based on manual testing
- Manual publish attempt revealed missing automation steps
- **ZERO** publish_result.json files found (never completed end-to-end)

**Content Tab Automation (2026-03-14):**
Based on manual KDP publish attempt for Priscilla's book, added:
1. **ISBN Assignment** - Select "Get a free KDP ISBN" radio → Click "Assign ISBN"
2. **Print Options** - Expand section if collapsed
3. **Ink & Paper** - Select "Premium Color" (required for picture books)
4. **Trim Size** - Select 8.5 x 8.5 in from dropdown
5. **Bleed** - Select "No bleed" (our PDFs don't include bleed margins)
6. **Cover Finish** - Select "Glossy"
7. **Reading Direction** - Select "Left to Right"
8. **Manuscript Upload** - Upload interior PDF with processing wait
9. **Cover Upload** - Upload cover PDF with processing wait

**Issues:**
- Never run in production
- CSS selectors need validation against live KDP UI
- No screenshot capture on failure

**Next Steps:**
1. **First real publish:** Priscilla's Magical Forest Adventure
2. Use dry-run mode first to validate selectors
3. Add screenshot capture for debugging

---

## Active Books in Pipeline

### Ready for Publishing
| Book | Location | Interior | Cover | Kindle | Status |
|------|----------|----------|-------|--------|--------|
| Priscillas_Magical_Forest_Adventure | output/ | 22MB | 56KB | 815KB | **READY TO PUBLISH** |
| Thomass_New_Friend | output/ChildrensBook/ | 15MB | 75KB | 798KB | Ready |
| Bianca_the_Cyborg_Cows_Space_Adventure | output/ | 10MB | 57KB | 649KB | Ready |
| Carl_and_the_Enchanted_Forest | output/ | 15KB⚠️ | 65KB | 972KB | Needs rebuild |
| Christopher_and_the_Magical_Cars | output/ | 15MB | 69KB | 869KB | Ready |

### In Progress
| Book | Stage | Issue |
|------|-------|-------|
| Panda Pippin | Art | Spreads not in art_result.json |
| Thomas Rainbow Friendship | Art | Spreads array empty |
| Thomas Rainbow of Friends | Story | No art generated |

---

## Recommended Next Actions

### Priority 1: First KDP Publish
1. **Publish Priscilla's book** - Complete with all 3 files
2. Validate KDP selectors work with current UI
3. Document any required manual interventions

### Priority 2: Fix Pipeline Breaks
4. Rebuild Carl's interior PDF (currently 15KB)
5. Fix incomplete art_result.json files
6. Add PDF size validation

### Priority 3: Technical Debt
7. Fix competition score formula in niche researcher
8. Update ARCHITECTURE.md (Claude → OpenAI)
9. Add macOS font support to PDF builder

---

## Quick Reference

**Start Dashboard:** `python run.py` → http://localhost:5555

**External Access:**
- URL: https://bookfactory.backtoirl.com
- Start tunnel: `cloudflared tunnel run bookfactory`

**Configuration:** `config/studio_config.yaml`

**Output Structure:**
```
output/
├── ChildrensBook/{Title}-{timestamp}/
│   ├── brief.json, story_package.json
│   ├── art/, *.pdf
└── ColoringBook/{Title}-{timestamp}/
    ├── coloring_brief.json, reference_sheet.png
    └── pages/, *.pdf
```
