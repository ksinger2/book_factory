# Book Factory - Session Context & Next Steps

> **Last Updated:** 2026-03-11 21:05 (via `/reinit`)
> **Session ID:** reinit-20260311

---

## Agent Status Reports

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

**Recent Changes:**
- **Model upgrade:** gpt-4o → gpt-image-1
- Added reference image support for character likeness from photos
- New "Character DNA" system for consistency across scenes
- Improved prompt structure following `prompting_skill.md` guidelines
- Style cascade: method param → story_package → instance → DEFAULT_STYLE

**Current State:**
- 9 books with successful art_result.json completions
- Most recent success: Christopher_and_the_Magical_Cars (12 spreads, cover, character sheet)
- Back cover generation returning `null` in some runs

**Next Steps:**
- Investigate back_cover generation (exists in code but not triggering)
- **FIX QA BUG:** `qa_check()` uses Anthropic API format but client is OpenAI - silent failure
- Evaluate upgrading to gpt-image-1.5 for better consistency

**Blockers/Notes:**
- **Critical Bug:** QA vision check broken (wrong API client)
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

### Active Books in Pipeline

| Book ID | Status | Stage | Next Action |
|---------|--------|-------|-------------|
| Priscillas_Magical_Forest_Adventure-20260307 | **COMPLETE** | PDF Done | Ready to publish |
| Christopher_and_the_Magical_Cars-20260308 | Art Done | Cover Only | Needs Interior.pdf |
| Christophers_Magical_Car_Journey-20260307 | Art Incomplete | Partial Art | Needs art regeneration |

### Configuration State
- `config/studio_config.yaml` properly configured
- Chrome Profile 2 set for KDP automation
- Art quality: high, QA: enabled, retries: 3
- Pricing: $9.99 paperback, $4.99 eBook

### Known Issues
1. **Art Pipeline QA broken** - uses wrong API client (Anthropic format, OpenAI client)
2. **Competition scores always 0** - Niche researcher formula issue
3. **ARCHITECTURE.md outdated** - still references Claude for story generation

### Uncommitted Changes
- niche_researcher.py (recursion fix)
- story_engine.py (API migration)
- art_pipeline.py (gpt-image-1 upgrade)
- pdf_builder.py (filename standardization)
- kdp_publisher.py (profile selection)

---

## Recommended Next Actions

Based on agent analysis, prioritized by impact:

1. **Fix Art Pipeline QA bug** - Critical: QA checks silently failing
2. **Publish Priscilla's book** - Ready for KDP, test the full pipeline
3. **Generate Interior.pdf for Christopher** - Art complete, needs PDF build
4. **Commit all pending changes** - Multiple important fixes uncommitted
5. **Update ARCHITECTURE.md** - Documentation out of sync with code

---

## Quick Links for Agents

| Agent | Primary Docs | Config |
|-------|--------------|--------|
| Niche Researcher | `ARCHITECTURE.md` | `config/studio_config.yaml` (research section) |
| Story Engine | `resources/grammar_guide.txt`, `ARCHITECTURE.md` | `config/studio_config.yaml` (defaults) |
| Art Pipeline | `prompting_skill.md`, `ARCHITECTURE.md` | `config/studio_config.yaml` (art section) |
| PDF Builder | `ARCHITECTURE.md` | `config/studio_config.yaml` (defaults) |
| KDP Publisher | `ARCHITECTURE.md` | `config/studio_config.yaml` (kdp section) |
