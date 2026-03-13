"""
Coloring Book PDF Builder

Builds KDP-ready PDFs for coloring books:
- Interior PDF with all line art pages
- Wraparound cover PDF with spine
- Kindle cover JPG
"""

import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass

from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.colors import white, black, HexColor
from PIL import Image as PILImage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ColoringBookPackage:
    """Complete coloring book package for PDF building."""
    title: str
    author: str
    theme: str
    age_level: str
    num_pages: int
    trim_size: str = "8.5x8.5"
    bleed: float = 0.125


class ColoringPDFBuilder:
    """
    Builds KDP-compliant PDFs for coloring books.

    Creates:
    - Interior PDF with coloring pages (no text overlays)
    - Wraparound cover PDF with spine calculation
    - Kindle cover JPG at proper dimensions
    """

    # Standard KDP trim sizes (inches)
    TRIM_SIZES = {
        "8.5x8.5": (8.5, 8.5),
        "8x10": (8.0, 10.0),
        "6x9": (6.0, 9.0),
    }

    # KDP minimum page counts
    MIN_PAGES = 24
    COLOR_QUALITY_DPI = 300

    def __init__(self, trim_size: str = "8.5x8.5", bleed: float = 0.125):
        """
        Initialize the PDF builder.

        Args:
            trim_size: One of "8.5x8.5", "8x10", "6x9"
            bleed: Bleed in inches (standard is 0.125)
        """
        if trim_size not in self.TRIM_SIZES:
            raise ValueError(f"Unknown trim size: {trim_size}. Use: {list(self.TRIM_SIZES.keys())}")

        self.trim_width, self.trim_height = self.TRIM_SIZES[trim_size]
        self.bleed = bleed
        self.page_width = (self.trim_width + 2 * self.bleed) * inch
        self.page_height = (self.trim_height + 2 * self.bleed) * inch

        logger.info(f"ColoringPDFBuilder initialized: {trim_size}, bleed={bleed}in")

    def build_interior(
        self,
        package: ColoringBookPackage,
        pages_dir: str,
        output_path: str
    ) -> bool:
        """
        Build KDP interior PDF with coloring pages.

        Structure:
        - Page 1: Title page
        - Page 2: Copyright page
        - Pages 3-N: Coloring pages
        - Remaining: Blank padding to reach minimum

        Coloring pages are full-bleed with NO text overlays.

        Args:
            package: ColoringBookPackage with book details
            pages_dir: Directory containing page_XX.png files
            output_path: Where to save the PDF

        Returns:
            True if successful
        """
        logger.info(f"Building coloring book interior PDF: {output_path}")

        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            pages_path = Path(pages_dir)

            # Create PDF canvas
            c = canvas.Canvas(str(output_file), pagesize=(self.page_width, self.page_height))
            page_num = 1

            # Page 1: Title page
            logger.info("Adding title page")
            self._draw_title_page(c, package)
            c.showPage()
            page_num += 1

            # Page 2: Copyright page
            logger.info("Adding copyright page")
            self._draw_copyright_page(c, package)
            c.showPage()
            page_num += 1

            # Page 3: Instructions page (optional for coloring books)
            logger.info("Adding instructions page")
            self._draw_instructions_page(c, package)
            c.showPage()
            page_num += 1

            # Coloring pages - find all page_XX.png files
            page_files = sorted(pages_path.glob("page_*.png"))

            if not page_files:
                # Try alternate naming: scene_XX.png
                page_files = sorted(pages_path.glob("scene_*.png"))

            for i, page_file in enumerate(page_files[:package.num_pages]):
                logger.info(f"Adding coloring page {i + 1}/{len(page_files)}")
                self._draw_coloring_page(c, page_file)
                c.showPage()
                page_num += 1

            # Padding to reach minimum page count
            while page_num < self.MIN_PAGES:
                # Add blank coloring-friendly pages
                self._draw_blank_page(c)
                c.showPage()
                page_num += 1

            # Save PDF
            c.save()
            logger.info(f"Interior PDF created: {output_file} ({page_num} pages)")
            return True

        except Exception as e:
            logger.error(f"Failed to build interior PDF: {str(e)}")
            return False

    def build_cover(
        self,
        package: ColoringBookPackage,
        cover_path: str,
        back_cover_path: str,
        output_path: str,
        page_count: int
    ) -> bool:
        """
        Build wraparound cover PDF (back + spine + front).

        Args:
            package: ColoringBookPackage with book details
            cover_path: Path to front cover image
            back_cover_path: Path to back cover image
            output_path: Where to save the PDF
            page_count: Total interior page count for spine calculation

        Returns:
            True if successful
        """
        logger.info(f"Building wraparound cover PDF: {output_path}")

        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Calculate spine width (80lb paper = 0.0035" per page)
            paper_thickness = 0.0035
            spine_width = (page_count * paper_thickness) + (2 * self.bleed)

            # Total cover dimensions
            back_width = self.trim_width + self.bleed
            cover_width = back_width + spine_width + self.trim_width + self.bleed
            cover_height = self.trim_height + (2 * self.bleed)

            # Create cover image
            cover_width_px = int(cover_width * self.COLOR_QUALITY_DPI)
            cover_height_px = int(cover_height * self.COLOR_QUALITY_DPI)

            logger.info(f"Cover dimensions: {cover_width:.2f}x{cover_height:.2f} inches")

            # Create white canvas
            cover_image = PILImage.new('RGB', (cover_width_px, cover_height_px), (255, 255, 255))

            # Load and place back cover
            if Path(back_cover_path).exists():
                back_img = self._load_and_resize_cover(
                    back_cover_path,
                    (self.trim_width + self.bleed, self.trim_height + 2 * self.bleed)
                )
                cover_image.paste(back_img, (0, 0))

            # Load and place front cover
            if Path(cover_path).exists():
                front_img = self._load_and_resize_cover(
                    cover_path,
                    (self.trim_width + self.bleed, self.trim_height + 2 * self.bleed)
                )
                front_x = int((back_width + spine_width) * self.COLOR_QUALITY_DPI)
                cover_image.paste(front_img, (front_x, 0))

            # Add spine text
            self._add_spine_text(
                cover_image,
                package.title,
                package.author,
                back_width,
                spine_width,
                cover_height
            )

            # Save as PDF
            cover_image.save(str(output_file), 'PDF', quality=95, dpi=(300, 300))
            logger.info(f"Cover PDF created: {output_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to build cover PDF: {str(e)}")
            return False

    def build_kindle_cover(
        self,
        cover_image_path: str,
        output_path: str,
        size: Tuple[int, int] = (2560, 1600)
    ) -> bool:
        """
        Convert cover PNG to JPG for Kindle.

        Kindle requirements: 1600x2560 minimum, 2560x1600 landscape or portrait.
        For coloring books, we typically use portrait.

        Args:
            cover_image_path: Path to front cover image
            output_path: Where to save the JPG
            size: Target dimensions (width, height)

        Returns:
            True if successful
        """
        logger.info(f"Building Kindle cover: {output_path}")

        try:
            cover_file = Path(cover_image_path)
            if not cover_file.exists():
                logger.error(f"Cover image not found: {cover_file}")
                return False

            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Open and convert
            img = PILImage.open(cover_file)

            # Convert RGBA to RGB
            if img.mode == 'RGBA':
                background = PILImage.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background

            # Resize to fit Kindle dimensions
            img.thumbnail(size, PILImage.Resampling.LANCZOS)

            # Create canvas with white background
            final = PILImage.new('RGB', size, (255, 255, 255))
            offset = (
                (size[0] - img.width) // 2,
                (size[1] - img.height) // 2
            )
            final.paste(img, offset)

            # Save as JPG
            final.save(str(output_file), 'JPEG', quality=95, dpi=(300, 300))
            logger.info(f"Kindle cover created: {output_file} ({size[0]}x{size[1]})")
            return True

        except Exception as e:
            logger.error(f"Failed to build Kindle cover: {str(e)}")
            return False

    def build_all(
        self,
        package: ColoringBookPackage,
        pages_dir: str,
        cover_path: str,
        back_cover_path: str,
        output_dir: str
    ) -> Dict[str, bool]:
        """
        Build all three files: interior PDF, cover PDF, Kindle cover JPG.

        Args:
            package: ColoringBookPackage with book details
            pages_dir: Directory containing coloring pages
            cover_path: Path to front cover image
            back_cover_path: Path to back cover image
            output_dir: Directory to save output files

        Returns:
            Dict with success status for each file
        """
        logger.info(f"Building all coloring book files to: {output_dir}")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results = {}

        # Interior PDF
        interior_path = output_path / "Interior.pdf"
        results['interior'] = self.build_interior(package, pages_dir, str(interior_path))

        # Calculate page count for spine
        # Count pages: title + copyright + instructions + coloring pages + padding
        pages_path = Path(pages_dir)
        coloring_pages = len(list(pages_path.glob("page_*.png")))
        if coloring_pages == 0:
            coloring_pages = len(list(pages_path.glob("scene_*.png")))
        total_pages = max(self.MIN_PAGES, 3 + coloring_pages)

        # Cover PDF
        cover_pdf_path = output_path / "Cover.pdf"
        results['cover'] = self.build_cover(
            package, cover_path, back_cover_path,
            str(cover_pdf_path), total_pages
        )

        # Kindle Cover JPG
        kindle_path = output_path / "Kindle_Cover.jpg"
        results['kindle_cover'] = self.build_kindle_cover(cover_path, str(kindle_path))

        logger.info(f"Build complete: {results}")
        return results

    # ========== PRIVATE DRAWING METHODS ==========

    def _draw_title_page(self, c: canvas.Canvas, package: ColoringBookPackage):
        """Draw the title page for a coloring book."""
        # Light background
        c.setFillColor(HexColor("#FFFFFF"))
        c.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)

        # Title
        c.setFont("Helvetica-Bold", 44)
        c.setFillColor(HexColor("#2C2C2C"))
        c.drawCentredString(self.page_width / 2, self.page_height - inch * 2, package.title)

        # Theme
        c.setFont("Helvetica", 24)
        c.setFillColor(HexColor("#666666"))
        c.drawCentredString(self.page_width / 2, self.page_height - inch * 3, package.theme)

        # Author
        c.setFont("Helvetica", 20)
        c.setFillColor(HexColor("#4A4A4A"))
        c.drawCentredString(self.page_width / 2, self.page_height / 2, f"by {package.author}")

        # Age level
        c.setFont("Helvetica", 14)
        c.setFillColor(HexColor("#888888"))
        age_text = f"For {package.age_level.title()} Colorists"
        c.drawCentredString(self.page_width / 2, inch * 2, age_text)

    def _draw_copyright_page(self, c: canvas.Canvas, package: ColoringBookPackage):
        """Draw copyright page."""
        c.setFillColor(white)
        c.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)

        y_pos = self.page_height - inch * 1
        c.setFont("Helvetica", 10)
        c.setFillColor(black)

        texts = [
            f"Copyright © 2024 {package.author}",
            "All rights reserved.",
            "",
            "No part of this coloring book may be reproduced",
            "without written permission from the author.",
            "",
            "This book contains content generated with AI assistance.",
            "All content has been reviewed and curated by humans.",
            "",
            f"Theme: {package.theme}",
            f"Designed for {package.age_level.title()} colorists",
        ]

        for text in texts:
            c.drawString(inch * 0.75, y_pos, text)
            y_pos -= inch * 0.35

    def _draw_instructions_page(self, c: canvas.Canvas, package: ColoringBookPackage):
        """Draw instructions/tips page for coloring."""
        c.setFillColor(HexColor("#FAFAFA"))
        c.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)

        # Title
        c.setFont("Helvetica-Bold", 28)
        c.setFillColor(HexColor("#333333"))
        c.drawCentredString(self.page_width / 2, self.page_height - inch * 1, "Coloring Tips")

        # Tips based on age level
        tips = self._get_tips_for_age(package.age_level)

        y_pos = self.page_height - inch * 2
        c.setFont("Helvetica", 12)
        c.setFillColor(HexColor("#444444"))

        for tip in tips:
            c.drawString(inch * 0.75, y_pos, f"• {tip}")
            y_pos -= inch * 0.4

    def _get_tips_for_age(self, age_level: str) -> List[str]:
        """Get age-appropriate coloring tips."""
        tips = {
            "kid": [
                "Use your favorite colors!",
                "It's okay to color outside the lines - have fun!",
                "Try using different colors for each section.",
                "You can use crayons, colored pencils, or markers.",
            ],
            "tween": [
                "Start with light colors and build up darker shades.",
                "Try blending colors together for cool effects.",
                "Work from the center outward on detailed designs.",
                "Use fine-tip markers for small areas.",
            ],
            "teen": [
                "Experiment with color gradients and shading.",
                "Try complementary colors for striking effects.",
                "Use fine-tipped pens for intricate details.",
                "Consider the mood you want to create with your palette.",
            ],
            "ya": [
                "Explore color theory for harmonious combinations.",
                "Try layering colors for depth and dimension.",
                "Gel pens work great for adding highlights.",
                "Consider leaving some areas white for contrast.",
            ],
            "adult": [
                "Take your time - this is about relaxation.",
                "Colored pencils offer the best control for details.",
                "Try different blending techniques.",
                "Work in sections to avoid smudging.",
                "Consider metallic or gel pens for accents.",
            ],
            "elder": [
                "Find comfortable lighting for your coloring session.",
                "Take breaks to rest your eyes and hands.",
                "Colored pencils are gentle and easy to control.",
                "There's no wrong way to color - enjoy the process!",
            ]
        }
        return tips.get(age_level.lower(), tips["adult"])

    def _draw_coloring_page(self, c: canvas.Canvas, image_path: Path):
        """Draw a full-bleed coloring page with no text."""
        if image_path.exists():
            # Load and resize image to full bleed
            img = PILImage.open(image_path)
            img = self._center_crop_image(img, self.page_width / inch, self.page_height / inch)

            # Save temporary image
            temp_path = Path("/tmp/temp_coloring_page.png")
            img.save(temp_path)

            # Draw full-bleed (no text overlay for coloring books)
            c.drawImage(str(temp_path), 0, 0, width=self.page_width, height=self.page_height)

            temp_path.unlink()
        else:
            # Fallback: white page
            c.setFillColor(white)
            c.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)

    def _draw_blank_page(self, c: canvas.Canvas):
        """Draw a blank white page."""
        c.setFillColor(white)
        c.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)

    def _center_crop_image(
        self,
        img: PILImage.Image,
        target_width_in: float,
        target_height_in: float
    ) -> PILImage.Image:
        """Fit image to target dimensions WITHOUT cropping.

        This ensures the main design is never cut off.
        If aspect ratios don't match, white space is added on sides.
        """
        target_width = int(target_width_in * self.COLOR_QUALITY_DPI)
        target_height = int(target_height_in * self.COLOR_QUALITY_DPI)

        img_aspect = img.width / img.height
        target_aspect = target_width / target_height

        # Scale to FIT (not fill) - entire image fits within target
        if img_aspect > target_aspect:
            # Image is wider than target - fit by width
            new_width = target_width
            new_height = int(new_width / img_aspect)
        else:
            # Image is taller than target - fit by height
            new_height = target_height
            new_width = int(new_height * img_aspect)

        img = img.resize((new_width, new_height), PILImage.Resampling.LANCZOS)

        # Create white background at target size and paste image centered
        result = PILImage.new('RGB', (target_width, target_height), (255, 255, 255))
        paste_x = (target_width - new_width) // 2
        paste_y = (target_height - new_height) // 2
        result.paste(img, (paste_x, paste_y))

        return result

    def _load_and_resize_cover(
        self,
        image_path: str,
        size_inches: Tuple[float, float]
    ) -> PILImage.Image:
        """Load and resize cover image."""
        img = PILImage.open(image_path)

        # Convert RGBA to RGB
        if img.mode == 'RGBA':
            background = PILImage.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background

        target_width = int(size_inches[0] * self.COLOR_QUALITY_DPI)
        target_height = int(size_inches[1] * self.COLOR_QUALITY_DPI)

        return img.resize((target_width, target_height), PILImage.Resampling.LANCZOS)

    def _add_spine_text(
        self,
        img: PILImage.Image,
        title: str,
        author: str,
        back_width: float,
        spine_width: float,
        cover_height: float
    ):
        """Add text to the spine of the cover."""
        from PIL import ImageDraw, ImageFont

        if spine_width < 0.3:  # Too narrow for text
            return

        draw = ImageDraw.Draw(img)

        # Calculate spine center
        spine_center_x = int((back_width + spine_width / 2) * self.COLOR_QUALITY_DPI)

        # Try to use a font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        except:
            font = ImageFont.load_default()

        # Rotate and draw title
        # This is simplified - for production you'd want proper text rotation
        # The text would be drawn vertically along the spine


def main():
    """Test the PDF builder."""
    builder = ColoringPDFBuilder(trim_size="8.5x8.5")

    package = ColoringBookPackage(
        title="Magical Mandalas",
        author="Creative Studio",
        theme="Mandalas & Patterns",
        age_level="adult",
        num_pages=24
    )

    print(f"PDF Builder initialized for {package.title}")
    print(f"Page dimensions: {builder.page_width/inch:.2f} x {builder.page_height/inch:.2f} inches")


if __name__ == "__main__":
    main()
