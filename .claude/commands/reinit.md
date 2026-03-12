# /reinit - Session Reinitialization Command

Re-synchronize all Book Factory agents with their domain knowledge and update session context.

## Instructions

Execute the following steps to reinitialize the session:

### Step 1: Launch All Domain Agents in Parallel

Use the Task tool to spawn 5 parallel agents, one for each domain. Each agent should:
1. Read their domain-specific documents
2. Read the current `NextSteps.md` file
3. Analyze recent changes in their domain (check git diff, recent output files)
4. Report back with their findings

**Agent 1 - Niche Researcher Agent:**
- Read: `agents/niche_researcher.py`, `config/studio_config.yaml` (research section), `ARCHITECTURE.md`
- Check: Recent `niche_report.json` files in output directories
- Report: Market research status, any new niches identified, configuration state

**Agent 2 - Story Engine Agent:**
- Read: `agents/story_engine.py`, `resources/grammar_guide.txt`, `ARCHITECTURE.md`
- Check: Recent `story.json`, `character.json`, `listing.json` files
- Report: Story generation capabilities, any recent stories created, quality metrics

**Agent 3 - Art Pipeline Agent:**
- Read: `agents/art_pipeline.py`, `prompting_skill.md`, `ARCHITECTURE.md`
- Check: Recent art directories, character sheets, QA results
- Report: Art generation status, character consistency state, any failed QA items

**Agent 4 - PDF Builder Agent:**
- Read: `agents/pdf_builder.py`, `ARCHITECTURE.md`
- Check: Recent PDF outputs, cover files, Kindle JPGs
- Report: PDF generation capabilities, any pending builds, format compliance

**Agent 5 - KDP Publisher Agent:**
- Read: `agents/kdp_publisher.py`, `config/studio_config.yaml` (kdp section), `ARCHITECTURE.md`
- Check: Recent `publish_result.json` files, KDP configuration state
- Report: Publishing status, any pending uploads, credential/config state

### Step 2: Synthesize Reports & Update NextSteps.md

After all agents report back:
1. Collect each agent's findings
2. Update the `NextSteps.md` file with:
   - Current timestamp
   - Each agent's "Recent Changes" section
   - Each agent's "Current State" section
   - Each agent's "Next Steps" section
   - Any blockers or notes
   - Active books in pipeline (scan output/ directory)
   - Recommended next actions based on all agent reports

### Step 3: Present Summary & Ask User

After updating NextSteps.md:
1. Summarize the current state of the Book Factory
2. List 3-5 recommended next actions based on agent findings
3. Use AskUserQuestion to ask the user what they'd like to do next

Provide options like:
- Run full pipeline (research → story → art → PDF → publish)
- Research new niches only
- Continue work on a specific book in progress
- Review/fix issues found by agents
- Custom task (let user specify)

---

## Example Output Format

After running `/reinit`, present something like:

```
Session Reinitialized

Niche Researcher: 3 viable niches identified, last scan 2 days ago
Story Engine: Ready, grammar guide loaded, no pending stories
Art Pipeline: 1 book with incomplete art (spread_08 failed QA)
PDF Builder: Ready, all recent builds successful
KDP Publisher: 2 books pending upload, credentials valid

Recommended Actions:
1. Fix failed art QA for [book-id] spread_08
2. Upload 2 pending books to KDP
3. Run new niche research (last scan >2 days)

What would you like to do next?
```

Then use AskUserQuestion with the top options.
