#!/usr/bin/env python3
"""
Comprehensive E2E tests for Book Factory.
Run with: python tests/test_book_factory.py

Tests cover:
- Dashboard loading
- Children's Book flow (story generation, character sheet, art)
- Coloring Book flow
- API endpoints
- Error handling
"""

import json
import asyncio
import sys
import traceback
from datetime import datetime
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:5555"
TIMEOUT = 10000  # 10 seconds

class TestResult:
    def __init__(self):
        self.tests = []
        self.errors = []

    def add(self, name: str, passed: bool, error: str = None, details: str = None):
        self.tests.append({
            "name": name,
            "passed": passed,
            "error": error,
            "details": details
        })
        if not passed and error:
            self.errors.append({"test": name, "error": error, "details": details})

    def summary(self) -> dict:
        passed = sum(1 for t in self.tests if t["passed"])
        failed = len(self.tests) - passed
        return {
            "total": len(self.tests),
            "passed": passed,
            "failed": failed,
            "success": failed == 0,
            "errors": self.errors
        }


async def test_server_running(page, results: TestResult):
    """Test 1: Server is running and dashboard loads"""
    try:
        response = await page.goto(BASE_URL, timeout=TIMEOUT)
        if response and response.status == 200:
            results.add("Server running", True)
        else:
            results.add("Server running", False, f"Status: {response.status if response else 'None'}")
    except Exception as e:
        results.add("Server running", False, str(e))


async def test_dashboard_elements(page, results: TestResult):
    """Test 2: Dashboard has required UI elements"""
    try:
        # Check for main navigation buttons
        childrens_btn = await page.locator("text=Children's Book").count()
        coloring_btn = await page.locator("text=Coloring Book").count()

        if childrens_btn > 0 and coloring_btn > 0:
            results.add("Dashboard UI elements", True)
        else:
            results.add("Dashboard UI elements", False,
                       f"Missing buttons: Children's={childrens_btn}, Coloring={coloring_btn}")
    except Exception as e:
        results.add("Dashboard UI elements", False, str(e))


async def test_childrens_book_navigation(page, results: TestResult):
    """Test 3: Can navigate through Children's Book steps"""
    try:
        await page.click("text=Children's Book", timeout=TIMEOUT)
        await page.wait_for_timeout(500)

        # Check sidebar steps exist
        steps = ["Brief", "Generate", "Output"]
        found_steps = 0
        for step in steps:
            count = await page.locator(f"text={step}").count()
            if count > 0:
                found_steps += 1

        if found_steps >= 2:  # At least Brief and Generate
            results.add("Children's Book navigation", True)
        else:
            results.add("Children's Book navigation", False,
                       f"Only found {found_steps}/3 steps")
    except Exception as e:
        results.add("Children's Book navigation", False, str(e))


async def test_sample_story_load(page, results: TestResult):
    """Test 4: Can load a sample story"""
    try:
        # Navigate to Generate step
        await page.click("text=Generate", timeout=5000)
        await page.wait_for_timeout(500)

        # Look for Sample button
        sample_btn = page.locator('button:has-text("[Sample]")')
        if await sample_btn.count() > 0:
            await sample_btn.click()
            await page.wait_for_timeout(2000)

            # Check if story preview appeared
            story_preview = await page.locator(".story-preview, .story-scene").count()
            regen_btn = await page.locator('button:has-text("Regenerate Story")').count()

            if story_preview > 0 or regen_btn > 0:
                results.add("Sample story load", True)
            else:
                results.add("Sample story load", False, "Story preview not found after loading sample")
        else:
            results.add("Sample story load", False, "[Sample] button not found")
    except Exception as e:
        results.add("Sample story load", False, str(e))


async def test_story_regen_modal(page, results: TestResult):
    """Test 5: Story regeneration modal works"""
    try:
        regen_btn = page.locator('button:has-text("Regenerate Story")')
        if await regen_btn.count() > 0:
            await regen_btn.click()
            await page.wait_for_timeout(300)

            modal = page.locator('#storyRegenModal')
            if await modal.is_visible():
                # Check modal elements
                textarea = await page.locator('#storyRegenFeedback').count()
                cancel = await page.locator('#storyRegenModal button:has-text("Cancel")').count()

                if textarea > 0 and cancel > 0:
                    # Close modal
                    await page.locator('#storyRegenModal button:has-text("Cancel")').click()
                    results.add("Story regen modal", True)
                else:
                    results.add("Story regen modal", False, "Modal missing elements")
            else:
                results.add("Story regen modal", False, "Modal did not appear")
        else:
            results.add("Story regen modal", False, "Regenerate Story button not found")
    except Exception as e:
        results.add("Story regen modal", False, str(e))


async def test_api_health(page, results: TestResult):
    """Test 6: API endpoints respond correctly"""
    try:
        # Test books list endpoint
        response = await page.request.get(f"{BASE_URL}/api/books")
        if response.status == 200:
            data = await response.json()
            if isinstance(data, dict) and "books" in data:
                results.add("API /api/books", True)
            else:
                results.add("API /api/books", False, f"Unexpected response format: {str(data)[:100]}")
        else:
            results.add("API /api/books", False, f"Status {response.status}")
    except Exception as e:
        results.add("API /api/books", False, str(e))


async def test_coloring_book_navigation(page, results: TestResult):
    """Test 7: Can navigate to Coloring Book flow"""
    try:
        await page.goto(BASE_URL, timeout=TIMEOUT)
        await page.wait_for_timeout(500)

        await page.click("text=Coloring Book", timeout=TIMEOUT)
        await page.wait_for_timeout(500)

        # Check for coloring book specific elements
        brief_elements = await page.locator("text=Theme, text=Title, select").count()

        if brief_elements > 0:
            results.add("Coloring Book navigation", True)
        else:
            # Try to find any input fields
            inputs = await page.locator("input, select, textarea").count()
            if inputs > 0:
                results.add("Coloring Book navigation", True)
            else:
                results.add("Coloring Book navigation", False, "No form elements found")
    except Exception as e:
        results.add("Coloring Book navigation", False, str(e))


async def test_image_regeneration_endpoint(page, results: TestResult):
    """Test 8: Image regeneration API structure"""
    try:
        # This tests the endpoint exists and handles errors gracefully
        response = await page.request.post(f"{BASE_URL}/api/regenerate-image",
            data=json.dumps({"book_id": "nonexistent"}),
            headers={"Content-Type": "application/json"})

        # Should return 400 or 404 for invalid book, not 500
        if response.status in [400, 404]:
            results.add("Image regen endpoint", True, details=f"Proper error handling: {response.status}")
        elif response.status == 500:
            body = await response.text()
            results.add("Image regen endpoint", False, f"Server error: {body[:200]}")
        else:
            results.add("Image regen endpoint", True, details=f"Status: {response.status}")
    except Exception as e:
        results.add("Image regen endpoint", False, str(e))


async def test_debug_mode_approval_endpoint(page, results: TestResult):
    """Test 9: Debug mode approval endpoint exists"""
    try:
        response = await page.request.post(f"{BASE_URL}/api/approve-image",
            data=json.dumps({"book_id": "test", "image_type": "spread", "index": 1}),
            headers={"Content-Type": "application/json"})

        # Should handle gracefully even if book doesn't exist
        if response.status in [200, 400, 404]:
            results.add("Debug approval endpoint", True, details=f"Status: {response.status}")
        else:
            body = await response.text()
            results.add("Debug approval endpoint", False, f"Unexpected status {response.status}: {body[:100]}")
    except Exception as e:
        results.add("Debug approval endpoint", False, str(e))


async def run_all_tests() -> TestResult:
    """Run all tests and return results"""
    results = TestResult()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Set default timeout
        page.set_default_timeout(TIMEOUT)

        print("=" * 60)
        print(f"Book Factory E2E Tests - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Run tests in order
        tests = [
            ("Server Running", test_server_running),
            ("Dashboard UI", test_dashboard_elements),
            ("Children's Book Nav", test_childrens_book_navigation),
            ("Sample Story Load", test_sample_story_load),
            ("Story Regen Modal", test_story_regen_modal),
            ("API Health", test_api_health),
            ("Coloring Book Nav", test_coloring_book_navigation),
            ("Image Regen Endpoint", test_image_regeneration_endpoint),
            ("Debug Approval Endpoint", test_debug_mode_approval_endpoint),
        ]

        for name, test_fn in tests:
            print(f"\n[{name}] Running...")
            try:
                await test_fn(page, results)
                last_result = results.tests[-1]
                if last_result["passed"]:
                    print(f"  ✓ Passed")
                else:
                    print(f"  ✗ Failed: {last_result['error']}")
            except Exception as e:
                print(f"  ✗ Exception: {e}")
                results.add(name, False, str(e), traceback.format_exc())

        await browser.close()

    # Print summary
    summary = results.summary()
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total: {summary['total']} | Passed: {summary['passed']} | Failed: {summary['failed']}")

    if summary['errors']:
        print("\nFAILURES:")
        for err in summary['errors']:
            print(f"  - {err['test']}: {err['error']}")

    print("=" * 60)

    return results


def main():
    results = asyncio.run(run_all_tests())
    summary = results.summary()

    # Output JSON for agent consumption
    print("\n[JSON_RESULT]")
    print(json.dumps(summary, indent=2))

    # Exit with error code if tests failed
    sys.exit(0 if summary['success'] else 1)


if __name__ == "__main__":
    main()
