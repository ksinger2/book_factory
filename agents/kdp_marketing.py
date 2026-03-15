#!/usr/bin/env python3
"""
KDP Marketing Agent for Book Factory

This agent analyzes published books and generates optimized marketing materials:
- Keyword research and optimization (7 keywords for KDP)
- Category suggestions (2-3 browse categories)
- SEO-optimized book description
- Title/subtitle optimization
- Amazon Ads campaign planning
- Social media content generation
- Quick wins checklist
"""

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class KeywordAnalysis:
    """A keyword with analysis metadata."""
    keyword: str
    search_volume: str  # "high", "medium", "low"
    competition: str    # "high", "medium", "low"
    relevance: int      # 1-10 score
    rationale: str


@dataclass
class CategorySuggestion:
    """A suggested KDP browse category."""
    path: str           # Full category path
    reasoning: str
    fit_score: int      # 1-10


@dataclass
class OptimizedListing:
    """Optimized book listing components."""
    title: str
    subtitle: str
    description: str    # HTML-formatted for KDP
    keywords: List[str] # 7 keywords
    categories: List[CategorySuggestion]


@dataclass
class AdKeyword:
    """A keyword for Amazon Ads."""
    keyword: str
    match_type: str     # "exact", "phrase", "broad"
    suggested_bid: float
    rationale: str


@dataclass
class AdCampaignPlan:
    """Amazon Ads campaign recommendation."""
    campaign_name: str
    daily_budget: float
    keywords: List[AdKeyword]
    targeting_strategy: str
    expected_acos: str  # "low", "medium", "high"


@dataclass
class SocialMediaPost:
    """Platform-specific marketing content."""
    platform: str       # "instagram", "facebook", "pinterest", "tiktok"
    content: str
    hashtags: List[str]
    best_posting_time: str
    content_type: str   # "image", "carousel", "video", "story"


@dataclass
class MarketingResult:
    """Complete marketing analysis output."""
    book_id: str
    book_title: str
    generated_at: str
    optimized_listing: OptimizedListing
    ad_campaign: Optional[AdCampaignPlan]
    social_posts: List[SocialMediaPost]
    quick_wins: List[str]
    competitor_insights: List[str]


class KDPMarketingAgent:
    """Agent for generating KDP marketing materials and optimization."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the KDPMarketingAgent.

        Args:
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package is required. Install with: pip install anthropic")

    def _call_api(self, system_prompt: str, user_prompt: str, max_retries: int = 3) -> str:
        """
        Call the Anthropic API with retry logic.

        Args:
            system_prompt: System message for Claude
            user_prompt: User message with the request
            max_retries: Number of retries on failure

        Returns:
            The model's response text
        """
        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4096,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                return response.content[0].text
            except Exception as e:
                logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise

    def _load_book_data(self, book_dir: str) -> dict:
        """
        Load book data from a book directory.

        Args:
            book_dir: Path to the book output directory

        Returns:
            Dictionary with book data (story, listing, brief, etc.)
        """
        book_path = Path(book_dir)
        data = {}

        # Load story package
        story_path = book_path / "story_package.json"
        if story_path.exists():
            with open(story_path) as f:
                data["story_package"] = json.load(f)

        # Load brief if available
        brief_path = book_path / "brief.json"
        if brief_path.exists():
            with open(brief_path) as f:
                data["brief"] = json.load(f)

        # Load coloring brief if it's a coloring book
        coloring_brief_path = book_path / "coloring_brief.json"
        if coloring_brief_path.exists():
            with open(coloring_brief_path) as f:
                data["coloring_brief"] = json.load(f)

        return data

    def analyze_keywords(self, book_data: dict) -> List[KeywordAnalysis]:
        """
        Analyze and generate optimized keywords for the book.

        Args:
            book_data: Dictionary with book information

        Returns:
            List of 7 KeywordAnalysis objects
        """
        story = book_data.get("story_package", {})
        brief = book_data.get("brief", {})
        coloring = book_data.get("coloring_brief", {})

        title = story.get("story", {}).get("title", "") or story.get("title", "")
        theme = brief.get("theme", "") or coloring.get("theme", "")
        category = brief.get("category", "")
        age_range = brief.get("ageRange", "") or coloring.get("ageLevel", "")
        animal = brief.get("animal", "")
        lesson = brief.get("lesson", "")

        system_prompt = """You are a KDP keyword optimization expert. Your job is to identify the 7 best keywords for a children's book listing on Amazon KDP.

Rules for KDP keywords:
- Each keyword can be up to 50 characters
- Use lowercase (Amazon is case-insensitive)
- No competitor brand names or author names
- Include a mix of specific and broad terms
- Consider what parents actually search for
- Include age-appropriate terms
- Consider seasonal/gift keywords if relevant

Respond in JSON format only."""

        user_prompt = f"""Analyze this children's book and provide 7 optimized keywords:

Title: {title}
Theme: {theme}
Category: {category}
Age Range: {age_range}
Main Character: {animal}
Core Lesson: {lesson}

Return exactly this JSON structure:
{{
  "keywords": [
    {{
      "keyword": "the keyword phrase",
      "search_volume": "high|medium|low",
      "competition": "high|medium|low",
      "relevance": 8,
      "rationale": "why this keyword works"
    }}
  ]
}}

Provide exactly 7 keywords."""

        response = self._call_api(system_prompt, user_prompt)

        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                keywords = []
                for kw in data.get("keywords", [])[:7]:
                    keywords.append(KeywordAnalysis(
                        keyword=kw.get("keyword", ""),
                        search_volume=kw.get("search_volume", "medium"),
                        competition=kw.get("competition", "medium"),
                        relevance=kw.get("relevance", 5),
                        rationale=kw.get("rationale", "")
                    ))
                return keywords
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse keyword response: {e}")

        return []

    def suggest_categories(self, book_data: dict) -> List[CategorySuggestion]:
        """
        Suggest optimal KDP browse categories.

        Args:
            book_data: Dictionary with book information

        Returns:
            List of 2-3 CategorySuggestion objects
        """
        story = book_data.get("story_package", {})
        brief = book_data.get("brief", {})
        coloring = book_data.get("coloring_brief", {})

        title = story.get("story", {}).get("title", "") or story.get("title", "")
        theme = brief.get("theme", "") or coloring.get("theme", "")
        age_range = brief.get("ageRange", "") or coloring.get("ageLevel", "")
        animal = brief.get("animal", "")
        is_coloring = bool(coloring)

        system_prompt = """You are a KDP category expert. Suggest the 2-3 best browse categories for maximum discoverability on Amazon.

Consider:
- Relevance to book content
- Competition level in category
- Category specificity (more specific = easier to rank)
- Age appropriateness

Respond in JSON format only."""

        book_type = "coloring book" if is_coloring else "children's picture book"
        user_prompt = f"""Suggest 2-3 KDP browse categories for this {book_type}:

Title: {title}
Theme: {theme}
Age Range: {age_range}
Main Character: {animal}

Return exactly this JSON structure:
{{
  "categories": [
    {{
      "path": "Books > Children's Books > Animals > Specific Animal",
      "reasoning": "why this category is good",
      "fit_score": 9
    }}
  ]
}}"""

        response = self._call_api(system_prompt, user_prompt)

        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                categories = []
                for cat in data.get("categories", [])[:3]:
                    categories.append(CategorySuggestion(
                        path=cat.get("path", ""),
                        reasoning=cat.get("reasoning", ""),
                        fit_score=cat.get("fit_score", 5)
                    ))
                return categories
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse category response: {e}")

        return []

    def optimize_description(self, book_data: dict) -> str:
        """
        Generate an SEO-optimized book description with HTML formatting.

        Args:
            book_data: Dictionary with book information

        Returns:
            HTML-formatted description for KDP
        """
        story = book_data.get("story_package", {})
        brief = book_data.get("brief", {})
        listing = story.get("listing", {})

        title = story.get("story", {}).get("title", "") or story.get("title", "")
        current_desc = listing.get("description", "")
        theme = brief.get("theme", "")
        age_range = brief.get("ageRange", "")
        animal = brief.get("animal", "")
        lesson = brief.get("lesson", "")

        system_prompt = """You are a children's book copywriter specializing in Amazon KDP descriptions.

Rules for KDP descriptions:
- Max 4,000 characters
- Use HTML: <b>, <i>, <br>, <h2> (no CSS, no links)
- Lead with emotional hook for parents
- Include age range clearly
- Mention key themes and lessons
- End with call to action
- Use bullet points for features
- Include social proof language

Write in a warm, engaging tone that appeals to gift-givers and parents."""

        user_prompt = f"""Write an optimized KDP book description:

Title: {title}
Current Description: {current_desc}
Theme: {theme}
Age Range: {age_range}
Main Character: {animal}
Core Lesson: {lesson}

Write a compelling 300-500 word description with HTML formatting for KDP."""

        return self._call_api(system_prompt, user_prompt)

    def optimize_title(self, book_data: dict) -> Tuple[str, str]:
        """
        Suggest optimized title and subtitle.

        Args:
            book_data: Dictionary with book information

        Returns:
            Tuple of (title, subtitle)
        """
        story = book_data.get("story_package", {})
        brief = book_data.get("brief", {})
        listing = story.get("listing", {})

        current_title = story.get("story", {}).get("title", "") or story.get("title", "")
        current_subtitle = listing.get("subtitle", "")
        theme = brief.get("theme", "")
        age_range = brief.get("ageRange", "")

        system_prompt = """You are a KDP title optimization expert.

Title rules:
- Max 200 characters total (title + subtitle)
- Title should be catchy and memorable
- Subtitle should include keywords and age info
- No excessive punctuation or ALL CAPS
- Include benefit or emotional hook

Respond in JSON format only."""

        user_prompt = f"""Optimize this book title and subtitle:

Current Title: {current_title}
Current Subtitle: {current_subtitle}
Theme: {theme}
Age Range: {age_range}

Return exactly this JSON structure:
{{
  "title": "Optimized Title",
  "subtitle": "SEO-optimized subtitle with age range and keywords"
}}"""

        response = self._call_api(system_prompt, user_prompt)

        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return (data.get("title", current_title), data.get("subtitle", current_subtitle))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse title response: {e}")

        return (current_title, current_subtitle)

    def create_ad_campaign(self, book_data: dict, keywords: List[KeywordAnalysis]) -> AdCampaignPlan:
        """
        Create an Amazon Ads campaign plan.

        Args:
            book_data: Dictionary with book information
            keywords: List of analyzed keywords

        Returns:
            AdCampaignPlan with recommended settings
        """
        story = book_data.get("story_package", {})
        title = story.get("story", {}).get("title", "") or story.get("title", "")
        keyword_list = [kw.keyword for kw in keywords]

        system_prompt = """You are an Amazon Ads expert for KDP books.

Consider:
- Children's books have lower margins
- Target ACoS of 30-50% for new books
- Start with exact match for testing
- Suggested bids based on competition
- Daily budget of $5-15 for testing

Respond in JSON format only."""

        user_prompt = f"""Create an Amazon Ads campaign plan for:

Title: {title}
Keywords available: {keyword_list}

Return exactly this JSON structure:
{{
  "campaign_name": "SP - {title[:30]} - Manual",
  "daily_budget": 10.0,
  "targeting_strategy": "Start with exact match on top 5 keywords, expand to phrase match after 2 weeks if ACoS is under 40%",
  "expected_acos": "medium",
  "keywords": [
    {{
      "keyword": "keyword phrase",
      "match_type": "exact",
      "suggested_bid": 0.50,
      "rationale": "why this bid"
    }}
  ]
}}

Include 5-7 keywords."""

        response = self._call_api(system_prompt, user_prompt)

        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                ad_keywords = []
                for kw in data.get("keywords", []):
                    ad_keywords.append(AdKeyword(
                        keyword=kw.get("keyword", ""),
                        match_type=kw.get("match_type", "exact"),
                        suggested_bid=kw.get("suggested_bid", 0.50),
                        rationale=kw.get("rationale", "")
                    ))
                return AdCampaignPlan(
                    campaign_name=data.get("campaign_name", f"SP - {title[:30]}"),
                    daily_budget=data.get("daily_budget", 10.0),
                    keywords=ad_keywords,
                    targeting_strategy=data.get("targeting_strategy", ""),
                    expected_acos=data.get("expected_acos", "medium")
                )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ad campaign response: {e}")

        return AdCampaignPlan(
            campaign_name=f"SP - {title[:30]}",
            daily_budget=10.0,
            keywords=[],
            targeting_strategy="Manual keyword targeting",
            expected_acos="medium"
        )

    def generate_social_content(self, book_data: dict) -> List[SocialMediaPost]:
        """
        Generate social media marketing content.

        Args:
            book_data: Dictionary with book information

        Returns:
            List of SocialMediaPost for different platforms
        """
        story = book_data.get("story_package", {})
        brief = book_data.get("brief", {})

        title = story.get("story", {}).get("title", "") or story.get("title", "")
        theme = brief.get("theme", "")
        age_range = brief.get("ageRange", "")
        lesson = brief.get("lesson", "")

        system_prompt = """You are a children's book marketing expert specializing in social media.

Create engaging posts for:
- Instagram (parents, visual focus)
- Facebook (parents, gift-givers)
- Pinterest (discovery, SEO-focused)
- TikTok (quick, engaging, trendy)

Each post should be platform-appropriate and include relevant hashtags.

Respond in JSON format only."""

        user_prompt = f"""Create social media posts for:

Title: {title}
Theme: {theme}
Age Range: {age_range}
Lesson: {lesson}

Return exactly this JSON structure:
{{
  "posts": [
    {{
      "platform": "instagram",
      "content": "Post caption here",
      "hashtags": ["hashtag1", "hashtag2"],
      "best_posting_time": "Tuesday 7pm EST",
      "content_type": "carousel"
    }}
  ]
}}

Create one post per platform (instagram, facebook, pinterest, tiktok)."""

        response = self._call_api(system_prompt, user_prompt)

        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                posts = []
                for post in data.get("posts", []):
                    posts.append(SocialMediaPost(
                        platform=post.get("platform", ""),
                        content=post.get("content", ""),
                        hashtags=post.get("hashtags", []),
                        best_posting_time=post.get("best_posting_time", ""),
                        content_type=post.get("content_type", "image")
                    ))
                return posts
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse social content response: {e}")

        return []

    def generate_quick_wins(self, book_data: dict) -> List[str]:
        """
        Generate a list of immediate actionable marketing tasks.

        Args:
            book_data: Dictionary with book information

        Returns:
            List of quick win action items
        """
        story = book_data.get("story_package", {})
        title = story.get("story", {}).get("title", "") or story.get("title", "")

        system_prompt = """You are a KDP marketing consultant. Generate a prioritized list of quick, actionable marketing tasks that an author can do immediately after publishing.

Focus on:
- Free marketing tactics
- Quick wins (< 30 minutes each)
- High impact activities
- No-cost or low-cost options

Respond in JSON format only."""

        user_prompt = f"""Generate 8-10 quick marketing wins for:

Title: {title}

Return exactly this JSON structure:
{{
  "quick_wins": [
    "Action item 1 - specific and actionable",
    "Action item 2 - specific and actionable"
  ]
}}"""

        response = self._call_api(system_prompt, user_prompt)

        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return data.get("quick_wins", [])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse quick wins response: {e}")

        return [
            "Request reviews from family and friends",
            "Share on social media with link",
            "Join children's book author groups",
            "Create Author Central page",
            "Set up A+ Content if eligible"
        ]

    def run(self, book_dir: str) -> MarketingResult:
        """
        Run the complete marketing analysis pipeline.

        Args:
            book_dir: Path to the book output directory

        Returns:
            MarketingResult with all analysis
        """
        logger.info(f"Starting marketing analysis for: {book_dir}")

        # Load book data
        book_data = self._load_book_data(book_dir)
        story = book_data.get("story_package", {})
        title = story.get("story", {}).get("title", "") or story.get("title", "")

        # Run all analyses
        logger.info("Analyzing keywords...")
        keywords = self.analyze_keywords(book_data)

        logger.info("Suggesting categories...")
        categories = self.suggest_categories(book_data)

        logger.info("Optimizing description...")
        description = self.optimize_description(book_data)

        logger.info("Optimizing title...")
        opt_title, opt_subtitle = self.optimize_title(book_data)

        logger.info("Creating ad campaign plan...")
        ad_campaign = self.create_ad_campaign(book_data, keywords)

        logger.info("Generating social content...")
        social_posts = self.generate_social_content(book_data)

        logger.info("Generating quick wins...")
        quick_wins = self.generate_quick_wins(book_data)

        # Build result
        result = MarketingResult(
            book_id=book_dir,
            book_title=title,
            generated_at=datetime.now().isoformat(),
            optimized_listing=OptimizedListing(
                title=opt_title,
                subtitle=opt_subtitle,
                description=description,
                keywords=[kw.keyword for kw in keywords],
                categories=categories
            ),
            ad_campaign=ad_campaign,
            social_posts=social_posts,
            quick_wins=quick_wins,
            competitor_insights=[]  # Could add competitor analysis in future
        )

        # Save result to book directory
        result_path = Path(book_dir) / "marketing_result.json"
        with open(result_path, 'w') as f:
            json.dump(asdict(result), f, indent=2, default=str)
        logger.info(f"Marketing result saved to: {result_path}")

        return result


def main():
    """Main entry point for testing the marketing agent."""
    import argparse

    parser = argparse.ArgumentParser(
        description="KDP Marketing Agent - Generate optimized marketing materials"
    )
    parser.add_argument(
        "book_dir",
        type=str,
        help="Path to the book output directory"
    )

    args = parser.parse_args()

    agent = KDPMarketingAgent()
    result = agent.run(args.book_dir)

    print("\n" + "=" * 60)
    print("MARKETING ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"\nTitle: {result.book_title}")
    print(f"\nOptimized Keywords:")
    for i, kw in enumerate(result.optimized_listing.keywords, 1):
        print(f"  {i}. {kw}")
    print(f"\nCategories:")
    for cat in result.optimized_listing.categories:
        print(f"  • {cat.path}")
    print(f"\nQuick Wins:")
    for win in result.quick_wins:
        print(f"  ☐ {win}")


if __name__ == "__main__":
    main()
