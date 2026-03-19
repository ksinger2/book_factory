# Book Factory - Session Context & Next Steps

> **Last Updated:** 2026-03-18
> **Session ID:** session-20260318a

---

## Session Reinitialized (2026-03-18)

All 5 domain agents have synchronized. Summary:

| Agent | Status | Key Finding |
|-------|--------|-------------|
| Niche Researcher | PLACEHOLDER | No functional agent - hardcoded briefs only |
| Story Engine | PRODUCTION | 25+ books, JSON repair added, debug mode working |
| Art Pipeline | READY | 18 books with art, moderation handling, cost-saving mode |
| PDF Builder | READY | 40+ builds, 2 phantom PDFs need rebuild |
| KDP Publisher | BLOCKED | Selector timeout on Content tab - needs live UI validation |

**Active Pipeline:** 35+ books generated in past week, 5 ready for KDP upload

---

## Latest Changes (2026-03-18)

### Listing JSON Token Limit Increase
Increased `max_tokens` for listing generation from 3072 → 4096 to prevent JSON truncation.

**Problem:** `Failed to parse listing JSON: Expecting ',' delimiter` — GPT was still truncating listing JSON mid-stream at 3072 tokens when descriptions contained multiple paragraphs, bullet points, and SEO content.

**Fix:** `agents/story_engine.py` line 715 — `max_tokens=3072` → `max_tokens=4096`

This now matches the token limit used for story generation (line 504).

### Story Engine Capitalization Fix
Removed brittle hardcoded capitalization post-processing and strengthened LLM prompts instead:

**Removed:**
- `_fix_capitalization()` method with 60+ word blocklist
- `_fix_story_capitalization()` wrapper method
- Post-processing call after JSON parsing

**Added:**
- Stronger CAPITALIZATION section in system prompts with clear examples:
  - WRONG: "The Happy Penguin Loved To Dance"
  - RIGHT: "The happy penguin loved to dance"
- Standard English rules (first word of sentence, proper nouns only)
- Updated both rhyming and prose prompts

**Rationale:** The word list approach was brittle (can never cover all words), unnecessary (LLM handles this with proper instructions), and hard to maintain.

### Bug Fixes — Story Generation (QA verified, live tested)

#### Fix 1: Listing JSON parse crash (root cause found)
**Problem:** `Failed to parse listing JSON: Expecting ',' delimiter` — listing prompt with 6 scene summaries was hitting the token cap and GPT was truncating the JSON mid-stream. No amount of repair logic can fix a truncated response.
**Solution:** Increased listing `max_tokens` from 2048 → 3072 → 4096 (final).

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
- `agents/story_engine.py` — listing max_tokens 2048→4096, json-repair fallback, capitalization rules
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

## Agent Status Summary (Updated 2026-03-18)

| Agent | Status | Recent Activity | Critical Issues |
|-------|--------|-----------------|-----------------|
| Niche Researcher | DISABLED | Hardcoded placeholder | Full agent removed - needs rebuild |
| Story Engine | PRODUCTION | 25+ books, JSON repair | Rhyme validation too sensitive |
| Art Pipeline | READY | 18 books with art, debug mode | Oliver's book missing spreads |
| PDF Builder | READY | 40+ builds successful | 2 phantom PDFs (Carl, Christopher) |
| KDP Publisher | BLOCKED | 0/2 publishes | Content tab selector timeout |
| KDP Marketing | NEW | Integrated in dashboard | Needs E2E testing |

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

## Recommended Next Actions (Updated 2026-03-18)

### Priority 1: Unblock KDP Publishing (CRITICAL)
1. **Fix Content tab selector** - Modal popover intercepting clicks
2. **First publish test:** Priscilla's Magical Forest Adventure (dry-run first)
3. Add screenshot capture on failure for debugging

### Priority 2: Fix Pipeline Issues
4. **Rebuild Carl's interior PDF** - Currently 15KB (phantom)
5. **Fix Oliver's art_result.json** - Missing spreads array
6. Add PDF size validation (detect <500KB interiors)

### Priority 3: Restore Research Capability
7. **Re-implement Niche Researcher** - Current placeholder uses hardcoded briefs
8. Create smart brief selector from existing niche_report.json (11 ranked niches)
9. Add market analysis using Claude API (replace broken scraping)

### Priority 4: Technical Debt
10. Fix rhyme validation algorithm (too many false positives)
11. Update ARCHITECTURE.md (Claude → OpenAI references)
12. Add macOS font path support to PDF builder

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
