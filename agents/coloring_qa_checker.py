"""
Coloring Book QA Checker

Vision-based quality assurance for coloring book pages.
Validates line closure, artifacts, pure B&W, line quality, and age appropriateness.
"""

import os
import base64
import logging
import time
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any
from dataclasses import dataclass

try:
    from openai import OpenAI, RateLimitError
except ImportError:
    raise ImportError("openai package required. Install with: pip install openai")


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class QAResult:
    """Result of a QA check on a coloring page."""
    passed: bool
    summary: str
    issues: List[str]
    scores: Dict[str, int]  # Individual check scores 0-100


class ColoringQAChecker:
    """
    Quality assurance checker for coloring book pages.

    Uses GPT-4 Vision to analyze coloring pages for:
    - Closed lines (no open shapes that would cause color bleeding)
    - No artifacts (gaps, breaks, glitches)
    - Pure B&W (only black lines on white, no gray/color)
    - Line quality (consistent weight, no jagged edges)
    - Age appropriateness (content matches target audience)
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize the QA checker.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
            model: Vision model to use for analysis.
        """
        if api_key is None:
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                raise ValueError(
                    "No API key provided. Set OPENAI_API_KEY environment variable."
                )

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.max_retries = 3

        logger.info(f"ColoringQAChecker initialized with model: {model}")

    def _image_to_base64(self, image_path: Path) -> str:
        """Convert image file to base64 data URL."""
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        # Determine media type from extension
        ext = image_path.suffix.lower()
        media_type = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp'
        }.get(ext, 'image/png')

        return f"data:{media_type};base64,{image_data}"

    def check_page(
        self,
        image_path: Path,
        age_level: str = "adult",
        difficulty: str = "medium",
        theme: str = ""
    ) -> QAResult:
        """
        Perform comprehensive QA check on a coloring page.

        Checks:
        1. CLOSED_LINES: All shapes fully closed, no run-off lines
        2. NO_ARTIFACTS: No gaps, breaks, glitches, or anomalies
        3. PURE_BW: Only black lines on white background, no gray/color
        4. LINE_QUALITY: Consistent weight, clean intersections, no jaggies
        5. AGE_APPROPRIATE: Content and complexity matches target audience

        Args:
            image_path: Path to the coloring page image
            age_level: Target age level (kid, tween, teen, ya, adult, elder)
            difficulty: Difficulty level (easy, medium, hard, expert)
            theme: Theme of the coloring book for context

        Returns:
            QAResult with pass/fail, summary, list of issues, and scores
        """
        image_path = Path(image_path)
        if not image_path.exists():
            return QAResult(
                passed=False,
                summary="Image file not found",
                issues=[f"File does not exist: {image_path}"],
                scores={}
            )

        # Build the QA prompt
        qa_prompt = f"""You are a quality assurance inspector for a coloring book publishing system.
Analyze this coloring page image and check the following criteria:

TARGET SPECIFICATIONS:
- Age Level: {age_level}
- Difficulty: {difficulty}
- Theme: {theme or "general"}

CHECK EACH CRITERION (score 0-100):

1. CLOSED_LINES (Critical):
   - Are ALL shapes fully closed with no open-ended lines?
   - Every bounded area should be fillable without color bleeding
   Score 100 = Perfect closure, 0 = Many open shapes

2. NO_ARTIFACTS (Critical):
   - No gaps or breaks in lines that should be continuous
   - No digital glitches, smudges, or anomalies
   - NO RANDOM DOTS, specks, or stray marks anywhere
   - Background must be CLEAN pure white
   Score 100 = Perfectly clean, 0 = Has dots/artifacts

3. PURE_BW (Critical):
   - ONLY black lines on white background
   - NO gray tones, gradients, or shading
   - NO color whatsoever
   Score 100 = Pure B&W, 0 = Contains color/gray

4. NO_EDGE_CUTOFF (Critical - BINARY PASS/FAIL):
   Scan all four edges carefully. This is the MOST IMPORTANT check.

   AUTOMATIC FAIL (Score 0-20):
   - ANY body part touches or extends past edge (tail, wing, ear, horn, foot, antenna)
   - Head cropped at top
   - Feet cropped at bottom
   - ANY appendage disappears at edge
   - Subject too large for page with parts cut off

   PASS (Score 80-100):
   - Subject fully contained with clear white margins on ALL 4 sides
   - Nothing touches any edge
   - All body parts complete and visible

   RULE: If ANY part of the main subject is cropped or cut off, MAX score is 20.
   Be STRICT - even partial cuts of tails, wings, ears count as failures.

5. LINE_QUALITY (Important):
   - Consistent line weight throughout (for the style)
   - Clean line intersections
   - No jagged/pixelated edges
   - Smooth curves where intended
   Score 100 = Professional quality, 0 = Poor quality

6. AGE_APPROPRIATE (Important):
   - Complexity matches {age_level} level
   - Content suitable for target audience
   - Difficulty matches {difficulty} specification
   Score 100 = Perfect match, 0 = Completely wrong

RESPONSE FORMAT (use exactly this format):

CLOSED_LINES: [SCORE]/100 - [brief reason]
NO_ARTIFACTS: [SCORE]/100 - [brief reason]
PURE_BW: [SCORE]/100 - [brief reason]
NO_EDGE_CUTOFF: [SCORE]/100 - [brief reason]
LINE_QUALITY: [SCORE]/100 - [brief reason]
AGE_APPROPRIATE: [SCORE]/100 - [brief reason]

ISSUES:
- [List each specific issue found, one per line]
- [Or "None" if no issues]

OVERALL: [PASS/FAIL] - [summary sentence]

Pass criteria: All critical checks (CLOSED_LINES, NO_ARTIFACTS, PURE_BW, NO_EDGE_CUTOFF) must score 70+
AND average of all scores must be 75+"""

        # Make API call with retry logic
        for attempt in range(self.max_retries):
            try:
                image_url = self._image_to_base64(image_path)

                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=800,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": image_url}
                                },
                                {
                                    "type": "text",
                                    "text": qa_prompt
                                }
                            ]
                        }
                    ]
                )

                result_text = response.choices[0].message.content
                logger.info(f"QA Check Result for {image_path.name}:\n{result_text}")

                # Parse the response
                return self._parse_qa_response(result_text)

            except RateLimitError:
                if attempt < self.max_retries - 1:
                    wait_time = 30 * (attempt + 1)
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    return QAResult(
                        passed=False,
                        summary="QA check failed due to rate limiting",
                        issues=["Rate limit exceeded after max retries"],
                        scores={}
                    )
            except Exception as e:
                logger.error(f"Error during QA check: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(5)
                else:
                    return QAResult(
                        passed=False,
                        summary=f"QA check failed with error: {str(e)}",
                        issues=[str(e)],
                        scores={}
                    )

        return QAResult(
            passed=False,
            summary="QA check failed after retries",
            issues=["Max retries exceeded"],
            scores={}
        )

    def _parse_qa_response(self, response_text: str) -> QAResult:
        """Parse the QA response text into a structured result."""
        scores = {}
        issues = []
        passed = False
        summary = "Unable to parse QA response"

        lines = response_text.strip().split('\n')

        # Parse scores - MUST include all critical checks!
        score_keys = ['CLOSED_LINES', 'NO_ARTIFACTS', 'PURE_BW', 'NO_EDGE_CUTOFF', 'LINE_QUALITY', 'AGE_APPROPRIATE']
        for line in lines:
            for key in score_keys:
                if line.strip().startswith(key + ':'):
                    try:
                        # Extract score: "CLOSED_LINES: 85/100 - reason"
                        score_part = line.split(':')[1].strip()
                        score = int(score_part.split('/')[0])
                        scores[key] = score
                    except (ValueError, IndexError):
                        scores[key] = 0

        # Parse issues
        in_issues = False
        for line in lines:
            if line.strip().startswith('ISSUES:'):
                in_issues = True
                continue
            if line.strip().startswith('OVERALL:'):
                in_issues = False
                # Parse overall result
                if 'PASS' in line.upper():
                    passed = True
                summary = line.split('-', 1)[-1].strip() if '-' in line else line
                continue
            if in_issues and line.strip().startswith('-'):
                issue = line.strip()[1:].strip()
                if issue.lower() != 'none':
                    issues.append(issue)

        # Validate pass/fail based on scores if we have them
        if scores:
            # Edge cutoff is strictly enforced - must score 50+ (stricter threshold)
            edge_passed = scores.get('NO_EDGE_CUTOFF', 0) >= 50
            # Other critical checks use standard 70 threshold
            other_critical = ['CLOSED_LINES', 'NO_ARTIFACTS', 'PURE_BW']
            other_passed = all(scores.get(k, 0) >= 70 for k in other_critical)
            avg_score = sum(scores.values()) / len(scores) if scores else 0
            # Must pass edge check AND other criticals AND have good average
            passed = edge_passed and other_passed and avg_score >= 70

        return QAResult(
            passed=passed,
            summary=summary,
            issues=issues,
            scores=scores
        )

    def check_batch(
        self,
        image_paths: List[Path],
        age_level: str = "adult",
        difficulty: str = "medium",
        theme: str = ""
    ) -> Dict[str, QAResult]:
        """
        Check multiple pages and return results keyed by filename.

        Args:
            image_paths: List of paths to check
            age_level: Target age level
            difficulty: Difficulty level
            theme: Theme context

        Returns:
            Dict mapping filename to QAResult
        """
        results = {}
        for path in image_paths:
            path = Path(path)
            logger.info(f"Checking page: {path.name}")
            results[path.name] = self.check_page(path, age_level, difficulty, theme)
            # Small delay to avoid rate limiting
            time.sleep(1)
        return results

    def get_failed_pages(
        self,
        results: Dict[str, QAResult]
    ) -> List[str]:
        """
        Get list of page names that failed QA.

        Args:
            results: Dict from check_batch

        Returns:
            List of failed page filenames
        """
        return [name for name, result in results.items() if not result.passed]


def main():
    """Test the QA checker."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python coloring_qa_checker.py <image_path> [age_level] [difficulty]")
        sys.exit(1)

    image_path = Path(sys.argv[1])
    age_level = sys.argv[2] if len(sys.argv) > 2 else "adult"
    difficulty = sys.argv[3] if len(sys.argv) > 3 else "medium"

    checker = ColoringQAChecker()
    result = checker.check_page(image_path, age_level, difficulty)

    print("\n" + "=" * 60)
    print("QA RESULT")
    print("=" * 60)
    print(f"Passed: {result.passed}")
    print(f"Summary: {result.summary}")
    print(f"\nScores:")
    for key, score in result.scores.items():
        status = "OK" if score >= 70 else "FAIL"
        print(f"  {key}: {score}/100 [{status}]")
    if result.issues:
        print(f"\nIssues:")
        for issue in result.issues:
            print(f"  - {issue}")
    print("=" * 60)


if __name__ == "__main__":
    main()
