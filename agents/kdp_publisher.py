"""
KDP Publisher Automation Module
Handles automated creation and publishing of children's books to Kindle Direct Publishing.
Uses Playwright for reliable browser automation instead of fragile Chrome extensions.
"""

import logging
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('kdp_publisher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class BookListing:
    """Book metadata for KDP publishing"""
    title: str
    subtitle: str
    author: str
    description: str
    categories: list  # List of 2 KDP category codes
    keywords: list  # List of keywords (max 7)
    ai_disclosure_text: str  # "Entire work, with extensive editing"
    ai_tool_text: str  # "Claude"
    ai_disclosure_images: str  # "Many AI-generated images, with extensive editing"
    ai_tool_images: str  # "ChatGPT"
    ai_disclosure_translation: str  # "None"


@dataclass
class BookPackage:
    """Complete book publishing package"""
    listing: BookListing
    interior_pdf_path: str
    cover_pdf_path: str
    cover_jpg_path: str
    us_price: float
    is_kdp_select: bool = True
    dry_run: bool = False


class KDPPublisher:
    """Automates KDP publishing workflows with Playwright"""

    KDP_HOME = "https://kdp.amazon.com/"
    KDP_BOOKSHELF = "https://kdp.amazon.com/en_US/bookshelf"
    KDP_NEW_TITLE = "https://kdp.amazon.com/en_US/title-setup/kindle/new/details"

    # Implicit wait times (seconds)
    WAIT_SHORT = 2
    WAIT_MEDIUM = 5
    WAIT_LONG = 10
    WAIT_FILE_UPLOAD = 15

    def __init__(self, headless: bool = False, debug: bool = False, use_chrome_profile: bool = True, chrome_profile_name: str = "Profile 2"):
        """Initialize KDP Publisher

        Args:
            headless: Run browser without GUI (won't work with use_chrome_profile)
            debug: Enable verbose logging
            use_chrome_profile: Launch using user's existing Chrome profile (reuses their KDP login)
            chrome_profile_name: Name of Chrome profile to use (e.g., "Default", "Profile 2")
        """
        self.headless = headless if not use_chrome_profile else False  # Chrome profile needs GUI
        self.debug = debug
        self.use_chrome_profile = use_chrome_profile
        self.chrome_profile_name = chrome_profile_name
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.session_file = Path("kdp_session.json")
        self._temp_profile_dir = None  # Track temp profile for cleanup
        logger.info(f"KDPPublisher initialized (headless={headless}, debug={debug}, chrome_profile={use_chrome_profile})")

    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()

    def _find_chrome_profile(self) -> Optional[str]:
        """Find the user's default Chrome profile directory"""
        import platform
        system = platform.system()

        candidates = []
        if system == "Darwin":  # macOS
            import os
            home = os.path.expanduser("~")
            candidates = [
                f"{home}/Library/Application Support/Google/Chrome",
                f"{home}/Library/Application Support/Google/Chrome Canary",
            ]
        elif system == "Linux":
            import os
            home = os.path.expanduser("~")
            candidates = [
                f"{home}/.config/google-chrome",
                f"{home}/.config/chromium",
            ]
        elif system == "Windows":
            import os
            local = os.environ.get("LOCALAPPDATA", "")
            candidates = [
                f"{local}\\Google\\Chrome\\User Data",
            ]

        for path in candidates:
            if Path(path).exists():
                logger.info(f"Found Chrome profile at: {path}")
                return path

        logger.warning("No Chrome profile found")
        return None

    def _copy_chrome_profile_to_temp(self, chrome_data_dir: str) -> Optional[str]:
        """Copy Chrome profile to a temp directory for Playwright use.

        Chrome doesn't allow DevTools on its default data directory,
        so we copy the profile to a temp location.
        """
        import shutil
        import tempfile

        source_profile = Path(chrome_data_dir) / self.chrome_profile_name
        if not source_profile.exists():
            logger.warning(f"Profile {self.chrome_profile_name} not found in {chrome_data_dir}")
            return None

        # Create temp directory for our copy
        temp_base = Path(tempfile.gettempdir()) / "kdp_publisher_profile"
        temp_base.mkdir(exist_ok=True)

        # Use a consistent temp profile directory
        temp_profile_dir = temp_base / "ChromeProfile"
        temp_profile_subdir = temp_profile_dir / "Default"  # Playwright expects "Default"

        # Copy essential profile files (cookies, local storage, login data)
        essential_items = [
            "Cookies",
            "Local Storage",
            "Session Storage",
            "Login Data",
            "Preferences",
            "Secure Preferences",
            "Web Data",
        ]

        try:
            # Clean up old temp profile
            if temp_profile_dir.exists():
                shutil.rmtree(temp_profile_dir)

            temp_profile_dir.mkdir(parents=True)
            temp_profile_subdir.mkdir()

            # Copy essential files/folders
            for item in essential_items:
                src = source_profile / item
                dst = temp_profile_subdir / item
                if src.exists():
                    if src.is_dir():
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
                    logger.debug(f"Copied {item}")

            # Also copy Local State from parent
            local_state = Path(chrome_data_dir) / "Local State"
            if local_state.exists():
                shutil.copy2(local_state, temp_profile_dir / "Local State")

            logger.info(f"Chrome profile copied to temp: {temp_profile_dir}")
            return str(temp_profile_dir)

        except Exception as e:
            logger.error(f"Failed to copy Chrome profile: {e}")
            return None

    def start(self):
        """Start Playwright and browser.

        Connects to existing Chrome via remote debugging if available (port 9222),
        otherwise falls back to fresh Playwright browser.
        """
        logger.info("Starting Playwright browser...")
        self.playwright = sync_playwright().start()

        # Try to connect to existing Chrome with remote debugging
        try:
            logger.info("Attempting to connect to Chrome on port 9222...")
            self.browser = self.playwright.chromium.connect_over_cdp("http://localhost:9222")
            self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            logger.info("Connected to existing Chrome browser via remote debugging!")
            return
        except Exception as e:
            logger.warning(f"Could not connect to Chrome remote debugging: {e}")

        # Try Chrome profile if enabled
        if self.use_chrome_profile:
            chrome_data_dir = self._find_chrome_profile()
            if chrome_data_dir:
                temp_profile = self._copy_chrome_profile_to_temp(chrome_data_dir)
                if temp_profile:
                    try:
                        logger.info(f"Launching browser with Chrome profile from {temp_profile}")
                        self._temp_profile_dir = temp_profile
                        self.context = self.playwright.chromium.launch_persistent_context(
                            user_data_dir=temp_profile,
                            headless=False,
                            channel="chromium",
                        )
                        self.browser = None  # persistent context acts as both browser and context
                        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
                        logger.info("Browser started with Chrome profile successfully")
                        return
                    except Exception as e:
                        logger.warning(f"Failed to launch with Chrome profile: {e}")
            else:
                logger.warning("Chrome profile not found, falling back to fresh browser")

        # Fallback: fresh Playwright browser with optional session file
        logger.info("Launching fresh Playwright browser...")
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        context_args = {
            'storage_state': str(self.session_file) if self.session_file.exists() else None
        }
        self.context = self.browser.new_context(**context_args)
        self.page = self.context.new_page()
        logger.info("Browser started successfully")

    def stop(self):
        """Stop browser and Playwright"""
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        # Clean up temp profile directory
        if self._temp_profile_dir:
            import shutil
            try:
                shutil.rmtree(self._temp_profile_dir, ignore_errors=True)
                logger.info(f"Cleaned up temp profile: {self._temp_profile_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp profile: {e}")
            self._temp_profile_dir = None
        logger.info("Browser stopped")

    def _log_action(self, action: str, details: str = ""):
        """Log action for debugging"""
        msg = f"[ACTION] {action}"
        if details:
            msg += f" - {details}"
        logger.info(msg)

    def _wait_for_navigation(self, timeout: int = WAIT_LONG):
        """Wait for page navigation to complete"""
        self.page.wait_for_load_state('networkidle', timeout=timeout * 1000)
        time.sleep(self.WAIT_SHORT)

    def _save_session(self):
        """Save browser session for future logins"""
        if self.context:
            self.context.storage_state(path=str(self.session_file))
            logger.info("Session saved to disk")

    def login(self, email: str, password: str) -> bool:
        """
        Login to KDP with email and password.
        Saves session for future automation.
        """
        self._log_action("LOGIN", f"email={email}")

        try:
            self.page.goto(self.KDP_HOME, wait_until='networkidle')
            self._wait_for_navigation()

            # Check if already logged in
            try:
                self.page.wait_for_selector('[data-feature-id="signout-button"]', timeout=3000)
                logger.info("Already logged in (found signout button)")
                return True
            except:
                pass

            # Click sign in button
            self._log_action("CLICKING", "sign-in button")
            sign_in_btn = self.page.locator('button:has-text("Sign in")')
            if sign_in_btn.count() > 0:
                sign_in_btn.first.click()
            else:
                # Try alternate selector
                self.page.click('a[href*="signin"]')

            self._wait_for_navigation()

            # Enter email
            self._log_action("ENTERING", "email address")
            email_input = self.page.locator('input[type="email"]')
            email_input.fill(email)
            self.page.click('input[id*="continue"]')

            self._wait_for_navigation(self.WAIT_MEDIUM)

            # Enter password
            self._log_action("ENTERING", "password")
            password_input = self.page.locator('input[type="password"]')
            password_input.fill(password)
            self.page.click('input[id*="signin"]')

            self._wait_for_navigation(self.WAIT_LONG)

            # Check for MFA or other verification
            try:
                self.page.wait_for_selector('[data-feature-id="auth-mfa"]', timeout=3000)
                logger.warning("MFA required - manual intervention needed")
                return False
            except:
                pass

            # Verify login success
            try:
                self.page.wait_for_selector('[data-feature-id="signout-button"]', timeout=5000)
                logger.info("Login successful")
                self._save_session()
                return True
            except:
                logger.error("Login verification failed")
                return False

        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            return False

    def _ensure_logged_in(self, max_wait_seconds: int = 180) -> bool:
        """
        Check if logged into KDP. If not, wait for manual login.
        Returns True if logged in, False if timeout reached.
        """
        self._log_action("CHECK_LOGIN", "Verifying KDP login status...")

        # Navigate to bookshelf to check login
        self.page.goto(self.KDP_BOOKSHELF, wait_until='networkidle')
        self._wait_for_navigation()

        # Check for signout button (indicates logged in)
        try:
            self.page.wait_for_selector('[data-feature-id="signout-button"], button:has-text("Sign out"), [aria-label*="sign out"]', timeout=5000)
            logger.info("Already logged into KDP")
            return True
        except:
            pass

        # Check if we're on login page
        current_url = self.page.url
        if 'signin' in current_url or 'ap/signin' in current_url:
            logger.info("Not logged in - waiting for manual login...")
            logger.info(f"Please log into KDP in the browser window. Waiting up to {max_wait_seconds} seconds...")
            print(f"\n{'='*60}")
            print("KDP LOGIN REQUIRED")
            print(f"{'='*60}")
            print("A browser window has opened. Please log into your KDP account.")
            print(f"Waiting up to {max_wait_seconds} seconds for login...")
            print(f"{'='*60}\n")

            # Wait for login (check for signout button periodically)
            import time
            start_time = time.time()
            while time.time() - start_time < max_wait_seconds:
                try:
                    self.page.wait_for_selector('[data-feature-id="signout-button"], button:has-text("Sign out"), [aria-label*="sign out"]', timeout=5000)
                    logger.info("Login detected! Continuing with publishing...")
                    self._save_session()  # Save session for future use
                    return True
                except:
                    pass
                time.sleep(2)

            logger.error(f"Login timeout after {max_wait_seconds} seconds")
            return False

        # Might be on bookshelf already, try to find create button
        try:
            self.page.wait_for_selector('button:has-text("Create"), button[data-test-id="create-new-title"]', timeout=5000)
            logger.info("On KDP bookshelf - logged in")
            return True
        except:
            pass

        logger.error("Could not verify KDP login status")
        return False

    def create_paperback(
        self,
        listing: BookListing,
        interior_pdf: str,
        cover_pdf: str,
        price: float,
        dry_run: bool = False
    ) -> bool:
        """
        Create a paperback title on KDP.
        Flow: Details → Content → Pricing → Publish
        """
        self._log_action("CREATE_PAPERBACK", f"title={listing.title}, price=${price}")

        try:
            # Ensure we're logged in first
            if not self._ensure_logged_in():
                logger.error("Not logged into KDP - cannot create paperback")
                return False

            # Navigate to bookshelf
            self.page.goto(self.KDP_BOOKSHELF, wait_until='networkidle')
            self._wait_for_navigation()

            # Check for account incomplete blocker
            if self._handle_account_incomplete_blocker():
                logger.warning("Account incomplete - cannot continue")
                return False

            # Click "+ Create new title"
            self._log_action("CLICKING", "+ Create new title button")
            create_btn = self.page.locator('button:has-text("Create new title"), button:has-text("Create New Title")')
            if create_btn.count() > 0:
                create_btn.first.click()
            else:
                # Try alternate selectors
                self.page.click('button[data-test-id="create-new-title"]')

            self._wait_for_navigation(self.WAIT_LONG)

            # Select Paperback option
            self._log_action("SELECTING", "Paperback format")
            paperback_option = self.page.locator('label:has-text("Paperback"), div:has-text("Paperback")')
            if paperback_option.count() > 0:
                paperback_option.first.click()
                self._wait_for_navigation(self.WAIT_MEDIUM)
            else:
                logger.warning("Could not find paperback option - attempting to continue")

            # Fill Details Tab
            self._log_action("FILLING", "Details tab")
            self._fill_details_tab(listing)

            # Move to Content Tab
            self._log_action("MOVING_TO", "Content tab")
            content_tab = self.page.locator('button[role="tab"]:has-text("Content"), a:has-text("Content")')
            if content_tab.count() > 0:
                content_tab.first.click()
                self._wait_for_navigation(self.WAIT_MEDIUM)

            # Fill Content Tab
            self._log_action("FILLING", "Content tab")
            self._fill_content_tab_paperback(interior_pdf, cover_pdf)

            # Move to Pricing Tab
            self._log_action("MOVING_TO", "Pricing tab")
            pricing_tab = self.page.locator('button[role="tab"]:has-text("Pricing"), a:has-text("Pricing")')
            if pricing_tab.count() > 0:
                pricing_tab.first.click()
                self._wait_for_navigation(self.WAIT_MEDIUM)

            # Fill Pricing Tab
            self._log_action("FILLING", "Pricing tab")
            self._fill_pricing_tab(price, listing.is_kdp_select if hasattr(listing, 'is_kdp_select') else True)

            # Publish
            if dry_run:
                logger.info("DRY RUN: Would click Publish now")
                return True
            else:
                self._log_action("PUBLISHING", "Paperback title")
                publish_btn = self.page.locator('button:has-text("Publish"), button:has-text("Save and Publish")')
                if publish_btn.count() > 0:
                    publish_btn.first.click()
                    self._wait_for_navigation(self.WAIT_LONG)
                    logger.info("Paperback published successfully")
                    return True
                else:
                    logger.error("Could not find publish button")
                    return False

        except Exception as e:
            logger.error(f"Paperback creation failed: {str(e)}")
            return False

    def create_ebook(
        self,
        listing: BookListing,
        interior_pdf: str,
        cover_jpg: str,
        price: float,
        dry_run: bool = False
    ) -> bool:
        """
        Create an eBook (Kindle) title on KDP.
        Similar to paperback but: PDF format, JPG cover, DRM enabled, 70% royalty
        """
        self._log_action("CREATE_EBOOK", f"title={listing.title}, price=${price}")

        try:
            # Ensure we're logged in first
            if not self._ensure_logged_in():
                logger.error("Not logged into KDP - cannot create ebook")
                return False

            # Navigate to bookshelf
            self.page.goto(self.KDP_BOOKSHELF, wait_until='networkidle')
            self._wait_for_navigation()

            # Check for account incomplete blocker
            if self._handle_account_incomplete_blocker():
                logger.warning("Account incomplete - cannot continue")
                return False

            # Click "+ Create new title"
            self._log_action("CLICKING", "+ Create new title button")
            create_btn = self.page.locator('button:has-text("Create new title"), button:has-text("Create New Title")')
            if create_btn.count() > 0:
                create_btn.first.click()
            else:
                self.page.click('button[data-test-id="create-new-title"]')

            self._wait_for_navigation(self.WAIT_LONG)

            # Select eBook option
            self._log_action("SELECTING", "eBook/Kindle format")
            ebook_option = self.page.locator('label:has-text("Kindle eBook"), label:has-text("eBook"), div:has-text("Kindle eBook")')
            if ebook_option.count() > 0:
                ebook_option.first.click()
                self._wait_for_navigation(self.WAIT_MEDIUM)

            # Fill Details Tab
            self._log_action("FILLING", "Details tab")
            self._fill_details_tab(listing)

            # Move to Content Tab
            self._log_action("MOVING_TO", "Content tab")
            content_tab = self.page.locator('button[role="tab"]:has-text("Content"), a:has-text("Content")')
            if content_tab.count() > 0:
                content_tab.first.click()
                self._wait_for_navigation(self.WAIT_MEDIUM)

            # Fill Content Tab (eBook variant)
            self._log_action("FILLING", "Content tab (eBook)")
            self._fill_content_tab_ebook(interior_pdf, cover_jpg)

            # Move to Pricing Tab
            self._log_action("MOVING_TO", "Pricing tab")
            pricing_tab = self.page.locator('button[role="tab"]:has-text("Pricing"), a:has-text("Pricing")')
            if pricing_tab.count() > 0:
                pricing_tab.first.click()
                self._wait_for_navigation(self.WAIT_MEDIUM)

            # Fill Pricing Tab (eBook: 70% royalty, DRM enabled)
            self._log_action("FILLING", "Pricing tab (eBook)")
            self._fill_pricing_tab_ebook(price, kdp_select=True)

            # Publish
            if dry_run:
                logger.info("DRY RUN: Would click Publish now")
                return True
            else:
                self._log_action("PUBLISHING", "eBook title")
                publish_btn = self.page.locator('button:has-text("Publish"), button:has-text("Save and Publish")')
                if publish_btn.count() > 0:
                    publish_btn.first.click()
                    self._wait_for_navigation(self.WAIT_LONG)
                    logger.info("eBook published successfully")
                    return True
                else:
                    logger.error("Could not find publish button")
                    return False

        except Exception as e:
            logger.error(f"eBook creation failed: {str(e)}")
            return False

    def publish_book(self, book_package: BookPackage) -> Dict[str, Any]:
        """
        Orchestrates full publishing of both paperback and eBook.
        Returns results dictionary.
        """
        self._log_action("PUBLISH_BOOK", f"title={book_package.listing.title}")

        results = {
            'timestamp': datetime.now().isoformat(),
            'title': book_package.listing.title,
            'paperback_success': False,
            'ebook_success': False,
            'errors': []
        }

        try:
            # Publish paperback
            logger.info("Publishing paperback...")
            paperback_ok = self.create_paperback(
                book_package.listing,
                book_package.interior_pdf_path,
                book_package.cover_pdf_path,
                book_package.us_price,
                dry_run=book_package.dry_run
            )
            results['paperback_success'] = paperback_ok
            if not paperback_ok:
                results['errors'].append("Paperback creation failed")

            # Add delay between publications
            time.sleep(self.WAIT_MEDIUM)

            # Publish eBook
            logger.info("Publishing eBook...")
            ebook_ok = self.create_ebook(
                book_package.listing,
                book_package.interior_pdf_path,
                book_package.cover_jpg_path,
                book_package.us_price,
                dry_run=book_package.dry_run
            )
            results['ebook_success'] = ebook_ok
            if not ebook_ok:
                results['errors'].append("eBook creation failed")

            logger.info(f"Publication complete: {results}")
            return results

        except Exception as e:
            logger.error(f"Publication workflow failed: {str(e)}")
            results['errors'].append(str(e))
            return results

    # ========== PRIVATE HELPER METHODS ==========

    def _handle_account_incomplete_blocker(self) -> bool:
        """
        Detects and handles the "Account Information Incomplete" blocker.
        Returns True if blocker is present and not resolved.
        """
        try:
            blocker = self.page.locator('text="Account Information Incomplete"')
            if blocker.count() > 0:
                logger.warning("Account Information Incomplete blocker detected")
                return True
        except:
            pass
        return False

    def _fill_details_tab(self, listing: BookListing):
        """Fill out the Details tab with book metadata"""
        try:
            # Title
            self._log_action("FILLING_FIELD", "Title")
            title_input = self.page.locator('input[name*="title"], input[aria-label*="Title"]')
            if title_input.count() > 0:
                title_input.first.fill(listing.title)

            # Subtitle (optional)
            self._log_action("FILLING_FIELD", "Subtitle")
            subtitle_input = self.page.locator('input[name*="subtitle"], input[aria-label*="Subtitle"]')
            if subtitle_input.count() > 0:
                subtitle_input.first.fill(listing.subtitle)

            # Author
            self._log_action("FILLING_FIELD", "Author")
            author_input = self.page.locator('input[name*="author"], input[aria-label*="Author"]')
            if author_input.count() > 0:
                author_input.first.fill(listing.author)

            # Description
            self._log_action("FILLING_FIELD", "Description")
            desc_input = self.page.locator('textarea[name*="description"], textarea[aria-label*="Description"]')
            if desc_input.count() > 0:
                desc_input.first.fill(listing.description)

            # Categories
            self._log_action("FILLING_FIELD", "Categories")
            for i, category in enumerate(listing.categories[:2]):  # Max 2 categories
                cat_input = self.page.locator('input[placeholder*="Search categories"], input[aria-label*="category"]')
                if cat_input.count() > i:
                    cat_input.nth(i).fill(category)
                    time.sleep(self.WAIT_SHORT)

            # Keywords
            self._log_action("FILLING_FIELD", "Keywords")
            keyword_input = self.page.locator('input[name*="keyword"], textarea[name*="keyword"]')
            if keyword_input.count() > 0:
                keywords_str = ", ".join(listing.keywords[:7])  # Max 7 keywords
                keyword_input.first.fill(keywords_str)

            # AI Disclosure - Text
            self._log_action("FILLING_FIELD", "AI Disclosure - Text")
            self._select_dropdown('AI-generated text disclosure', listing.ai_disclosure_text)

            # AI Disclosure - Text Tool
            if "extensive editing" in listing.ai_disclosure_text.lower():
                self._log_action("FILLING_FIELD", "AI Disclosure - Text Tool")
                self._select_dropdown('AI tool for text', listing.ai_tool_text)

            # AI Disclosure - Images
            self._log_action("FILLING_FIELD", "AI Disclosure - Images")
            self._select_dropdown('AI-generated images disclosure', listing.ai_disclosure_images)

            # AI Disclosure - Images Tool
            if "extensive editing" in listing.ai_disclosure_images.lower():
                self._log_action("FILLING_FIELD", "AI Disclosure - Images Tool")
                self._select_dropdown('AI tool for images', listing.ai_tool_images)

            # AI Disclosure - Translation
            self._log_action("FILLING_FIELD", "AI Disclosure - Translation")
            self._select_dropdown('AI translation disclosure', listing.ai_disclosure_translation)

            logger.info("Details tab filled successfully")

        except Exception as e:
            logger.error(f"Failed to fill Details tab: {str(e)}")

    def _fill_content_tab_paperback(self, interior_pdf: str, cover_pdf: str):
        """Fill Content tab for paperback

        KDP Content tab flow (in order):
        1. ISBN assignment (free KDP ISBN)
        2. Print options (ink/paper, trim size, bleed, cover finish)
        3. Manuscript upload
        4. Cover upload
        """
        try:
            # === SECTION 1: ISBN Assignment ===
            self._log_action("SELECTING", "Free KDP ISBN")
            # Select "Get a free KDP ISBN" radio button
            free_isbn_radio = self.page.locator(
                'input[type="radio"][value*="free"], '
                'label:has-text("Get a free KDP ISBN") input[type="radio"], '
                'div:has-text("Get a free KDP ISBN") input[type="radio"]'
            )
            if free_isbn_radio.count() > 0:
                free_isbn_radio.first.click()
                time.sleep(self.WAIT_SHORT)

            # Click "Assign ISBN" button
            self._log_action("CLICKING", "Assign ISBN button")
            assign_isbn_btn = self.page.locator(
                'button:has-text("Assign ISBN"), '
                'button:has-text("Assign an ISBN"), '
                'input[type="button"][value*="Assign"]'
            )
            if assign_isbn_btn.count() > 0:
                assign_isbn_btn.first.click()
                time.sleep(self.WAIT_MEDIUM)

            # === SECTION 2: Print Options ===
            # Expand print options section if collapsed
            print_options_header = self.page.locator(
                'button:has-text("Print options"), '
                'div[role="button"]:has-text("Print options"), '
                'h2:has-text("Print options")'
            )
            if print_options_header.count() > 0:
                # Check if section needs expanding (look for collapsed state)
                parent = print_options_header.first
                if parent.get_attribute('aria-expanded') == 'false':
                    parent.click()
                    time.sleep(self.WAIT_SHORT)

            # Ink and Paper Type - Select Premium Color
            self._log_action("SELECTING", "Ink and paper: Premium Color")
            premium_color = self.page.locator(
                'label:has-text("Premium color"), '
                'input[type="radio"][value*="premium"], '
                'div:has-text("Premium color") input[type="radio"]'
            )
            if premium_color.count() > 0:
                premium_color.first.click()
                time.sleep(self.WAIT_SHORT)

            # Trim Size - Select 8.5 x 8.5 in
            self._log_action("SELECTING", "Trim size: 8.5 x 8.5 in")
            # First try clicking the trim size dropdown/select
            trim_dropdown = self.page.locator(
                'select[name*="trim"], '
                '[aria-label*="Trim size"], '
                'div:has-text("Trim size") select'
            )
            if trim_dropdown.count() > 0:
                trim_dropdown.first.select_option(label="8.5 x 8.5 in")
            else:
                # Fallback: look for radio/button options
                trim_option = self.page.locator(
                    'label:has-text("8.5 x 8.5"), '
                    'option:has-text("8.5 x 8.5")'
                )
                if trim_option.count() > 0:
                    trim_option.first.click()
            time.sleep(self.WAIT_SHORT)

            # Bleed Settings - Select No Bleed (our PDFs don't have bleed margins)
            self._log_action("SELECTING", "Bleed: No bleed")
            no_bleed = self.page.locator(
                'label:has-text("No bleed"), '
                'input[type="radio"][value*="no-bleed"], '
                'input[type="radio"][value*="none"]'
            )
            if no_bleed.count() > 0:
                no_bleed.first.click()
                time.sleep(self.WAIT_SHORT)

            # Cover Finish - Select Glossy
            self._log_action("SELECTING", "Cover finish: Glossy")
            glossy_option = self.page.locator(
                'label:has-text("Glossy"), '
                'input[type="radio"][value*="glossy"], '
                'div:has-text("Glossy") input[type="radio"]'
            )
            if glossy_option.count() > 0:
                glossy_option.first.click()
                time.sleep(self.WAIT_SHORT)

            # Page Reading Direction - Left to Right (default for English)
            self._log_action("SELECTING", "Reading direction: Left to Right")
            ltr_option = self.page.locator(
                'label:has-text("Left to Right"), '
                'input[type="radio"][value*="ltr"], '
                'input[type="radio"][value*="left"]'
            )
            if ltr_option.count() > 0:
                ltr_option.first.click()
                time.sleep(self.WAIT_SHORT)

            # === SECTION 3: Manuscript Upload ===
            self._log_action("UPLOADING", f"interior PDF: {interior_pdf}")
            # Look for manuscript/interior upload input
            interior_input = self.page.locator(
                'input[type="file"][name*="interior"], '
                'input[type="file"][name*="manuscript"], '
                'input[type="file"][accept*="pdf"]'
            )
            if interior_input.count() > 0:
                interior_input.first.set_input_files(interior_pdf)
                # Wait for upload and processing
                time.sleep(self.WAIT_FILE_UPLOAD)
                # Wait for processing indicator to disappear
                self._wait_for_upload_complete()

            # === SECTION 4: Cover Upload ===
            self._log_action("UPLOADING", f"cover PDF: {cover_pdf}")
            # Cover upload is typically the second file input or specifically labeled
            cover_input = self.page.locator(
                'input[type="file"][name*="cover"]'
            )
            if cover_input.count() > 0:
                cover_input.first.set_input_files(cover_pdf)
            else:
                # Fallback: find all PDF inputs and use the second one
                all_pdf_inputs = self.page.locator('input[type="file"][accept*="pdf"]')
                if all_pdf_inputs.count() > 1:
                    all_pdf_inputs.nth(1).set_input_files(cover_pdf)
                elif all_pdf_inputs.count() > 0:
                    all_pdf_inputs.first.set_input_files(cover_pdf)

            # Wait for cover upload and processing
            time.sleep(self.WAIT_FILE_UPLOAD)
            self._wait_for_upload_complete()

            logger.info("Content tab (paperback) filled successfully")

        except Exception as e:
            logger.error(f"Failed to fill Content tab (paperback): {str(e)}")

    def _wait_for_upload_complete(self, timeout: int = 60):
        """Wait for file upload processing to complete"""
        try:
            # Wait for any processing spinner/indicator to disappear
            processing_indicators = [
                '[class*="spinner"]',
                '[class*="loading"]',
                '[class*="progress"]',
                'div:has-text("Processing")',
                'div:has-text("Uploading")'
            ]
            for indicator in processing_indicators:
                try:
                    locator = self.page.locator(indicator)
                    if locator.count() > 0:
                        locator.first.wait_for(state='hidden', timeout=timeout * 1000)
                except:
                    pass
        except Exception as e:
            logger.debug(f"Upload wait check: {str(e)}")

    def _fill_content_tab_ebook(self, interior_pdf: str, cover_jpg: str):
        """Fill Content tab for eBook"""
        try:
            # Upload interior PDF
            self._log_action("UPLOADING", f"interior PDF: {interior_pdf}")
            interior_input = self.page.locator('input[type="file"][name*="manuscript"], input[type="file"][accept*="pdf"]')
            if interior_input.count() > 0:
                interior_input.first.set_input_files(interior_pdf)
                time.sleep(self.WAIT_FILE_UPLOAD)

            # Upload cover JPG
            self._log_action("UPLOADING", f"cover JPG: {cover_jpg}")
            cover_input = self.page.locator('input[type="file"][name*="cover"], input[type="file"][accept*="jpg"], input[type="file"][accept*="image"]')
            if cover_input.count() > 0:
                cover_input.first.set_input_files(cover_jpg)
                time.sleep(self.WAIT_FILE_UPLOAD)

            # Enable DRM (Digital Rights Management)
            self._log_action("SELECTING", "DRM: Enabled")
            drm_checkbox = self.page.locator('input[type="checkbox"][aria-label*="DRM"], label:has-text("Enable DRM")')
            if drm_checkbox.count() > 0:
                drm_checkbox.first.check()

            logger.info("Content tab (eBook) filled successfully")

        except Exception as e:
            logger.error(f"Failed to fill Content tab (eBook): {str(e)}")

    def _fill_pricing_tab(self, us_price: float, kdp_select: bool = True):
        """Fill Pricing tab for paperback"""
        try:
            # Set US price
            self._log_action("SETTING", f"US price: ${us_price}")
            price_input = self.page.locator('input[name*="price"], input[aria-label*="price"]')
            if price_input.count() > 0:
                price_input.first.fill(str(us_price))

            # KDP Select
            if kdp_select:
                self._log_action("SELECTING", "KDP Select: Yes")
                kdp_select_checkbox = self.page.locator('input[type="checkbox"][aria-label*="KDP Select"]')
                if kdp_select_checkbox.count() > 0:
                    kdp_select_checkbox.first.check()

            logger.info("Pricing tab filled successfully")

        except Exception as e:
            logger.error(f"Failed to fill Pricing tab: {str(e)}")

    def _fill_pricing_tab_ebook(self, us_price: float, kdp_select: bool = True):
        """Fill Pricing tab for eBook (with 70% royalty option)"""
        try:
            # Set US price
            self._log_action("SETTING", f"US price: ${us_price}")
            price_input = self.page.locator('input[name*="price"], input[aria-label*="price"]')
            if price_input.count() > 0:
                price_input.first.fill(str(us_price))

            # Select 70% royalty option
            self._log_action("SELECTING", "Royalty: 70%")
            royalty_70 = self.page.locator('label:has-text("70%"), input[value="70"]')
            if royalty_70.count() > 0:
                royalty_70.first.click()

            # KDP Select
            if kdp_select:
                self._log_action("SELECTING", "KDP Select: Yes")
                kdp_select_checkbox = self.page.locator('input[type="checkbox"][aria-label*="KDP Select"]')
                if kdp_select_checkbox.count() > 0:
                    kdp_select_checkbox.first.check()

            logger.info("Pricing tab (eBook) filled successfully")

        except Exception as e:
            logger.error(f"Failed to fill Pricing tab (eBook): {str(e)}")

    def _select_dropdown(self, label: str, value: str):
        """Helper to select a dropdown option"""
        try:
            # Try to find and click dropdown
            dropdown = self.page.locator(f'select, [role="combobox"][aria-label*="{label}"]')
            if dropdown.count() > 0:
                dropdown.first.click()
                time.sleep(self.WAIT_SHORT)

                # Click option
                option = self.page.locator(f'text="{value}"')
                if option.count() > 0:
                    option.first.click()
        except Exception as e:
            logger.debug(f"Dropdown selection failed for {label}: {str(e)}")


def main():
    """Example usage"""
    import argparse

    parser = argparse.ArgumentParser(description="KDP Publisher Automation")
    parser.add_argument('--email', required=True, help='KDP email')
    parser.add_argument('--password', required=True, help='KDP password')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no publishing)')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    args = parser.parse_args()

    with KDPPublisher(headless=args.headless) as publisher:
        # Login
        if not publisher.login(args.email, args.password):
            logger.error("Login failed")
            return

        # Example book
        listing = BookListing(
            title="The Amazing Adventures of Pixel",
            subtitle="A Children's Tale",
            author="Creative Studio",
            description="Join Pixel on an magical journey through a digital wonderland...",
            categories=["Juvenile Fiction", "Illustrated Stories"],
            keywords=["adventure", "children", "fantasy", "digital", "AI illustrated"],
            ai_disclosure_text="Entire work, with extensive editing",
            ai_tool_text="Claude",
            ai_disclosure_images="Many AI-generated images, with extensive editing",
            ai_tool_images="ChatGPT",
            ai_disclosure_translation="None"
        )

        book = BookPackage(
            listing=listing,
            interior_pdf_path="/path/to/interior.pdf",
            cover_pdf_path="/path/to/cover.pdf",
            cover_jpg_path="/path/to/cover.jpg",
            us_price=12.99,
            is_kdp_select=True,
            dry_run=args.dry_run
        )

        # Publish
        results = publisher.publish_book(book)
        print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
