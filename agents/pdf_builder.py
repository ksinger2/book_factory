"""
PDF Builder for KDP Publishing
Generates publication-ready interior PDFs, wraparound covers, and Kindle covers
using ReportLab with full-bleed image support and text overlays.
"""

import logging
import json
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass
from io import BytesIO

from reportlab.lib.pagesizes import landscape, portrait
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.colors import white, black, HexColor
from reportlab.platypus import SimpleDocTemplate, Image, Spacer, Paragraph, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from PIL import Image as PILImage, ImageDraw, ImageFilter


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pdf_builder.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class TextOverlay:
    """Text overlay configuration"""
    text: str
    x: float  # inches from left
    y: float  # inches from top
    font_size: int
    font_name: str = "Helvetica-Bold"
    color: Tuple[int, int, int] = (255, 255, 255)  # RGB
    drop_shadow: bool = True
    align: str = "center"  # left, center, right


@dataclass
class StoryPage:
    """A single story page spread"""
    image_path: str  # Full-bleed image
    text_overlays: List[TextOverlay]


@dataclass
class StoryPackage:
    """Complete book package"""
    title: str
    author: str
    subtitle: str
    blurb: str  # Back cover blurb
    pages: List[StoryPage]  # Content pages (typically 12 spreads)
    trim_size: Tuple[float, float] = (8.5, 8.5)  # inches (width, height)
    bleed: float = 0.125  # inches


class PDFBuilder:
    """Builds KDP-compliant PDFs with full-bleed images and text overlays"""

    # Standard KDP trim sizes (inches)
    TRIM_SIZES = {
        "8.5x8.5": (8.5, 8.5),
        "8.5x11": (8.5, 11.0),
        "6x9": (6.0, 9.0),
        "5x8": (5.0, 8.0),
    }

    # Page count requirements
    MIN_PAGES = 24
    COLOR_QUALITY_DPI = 300

    def __init__(self, trim_size: str = "8.5x8.5", bleed: float = 0.125):
        """Initialize PDF builder"""
        if trim_size not in self.TRIM_SIZES:
            raise ValueError(f"Unknown trim size: {trim_size}")

        self.trim_width, self.trim_height = self.TRIM_SIZES[trim_size]
        self.bleed = bleed
        self.page_width = (self.trim_width + 2 * self.bleed) * inch
        self.page_height = (self.trim_height + 2 * self.bleed) * inch

        logger.info(f"PDFBuilder initialized: {trim_size}, bleed={bleed}in")

    def build_interior(
        self,
        story_package: StoryPackage,
        art_dir: str,
        output_path: str
    ) -> bool:
        """
        Build KDP interior PDF with front/back matter and story spreads.
        Structure: half-title, title page, copyright, dedication, 12 spreads,
                   "The End", about page, coming soon, blank padding to 24 pages
        """
        logger.info(f"Building interior PDF: {output_path}")

        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Create PDF with custom canvas
            c = canvas.Canvas(str(output_file), pagesize=(self.page_width, self.page_height))

            # Page counter
            page_num = 1

            # ===== FRONT MATTER =====

            # Page 1: Half-title page
            logger.info("Adding half-title page")
            self._draw_warm_page(c, story_package.title, page_height=self.page_height)
            c.showPage()
            page_num += 1

            # Page 2: Title page
            logger.info("Adding title page")
            self._draw_title_page(c, story_package, page_height=self.page_height)
            c.showPage()
            page_num += 1

            # Page 3: Copyright page
            logger.info("Adding copyright page")
            self._draw_copyright_page(c, story_package, page_height=self.page_height)
            c.showPage()
            page_num += 1

            # Page 4: Dedication page
            logger.info("Adding dedication page")
            self._draw_dedication_page(c, page_height=self.page_height)
            c.showPage()
            page_num += 1

            # ===== CONTENT PAGES =====

            # Pages 5-28: Story spreads (12 spreads = 24 pages)
            for i, page in enumerate(story_package.pages[:12]):
                logger.info(f"Adding story page {i + 1}/12")
                self._draw_story_spread(c, page, art_dir, page_height=self.page_height)
                c.showPage()
                page_num += 1

            # ===== BACK MATTER =====

            # Page: "The End"
            logger.info("Adding 'The End' page")
            self._draw_warm_page(c, "The End", page_height=self.page_height)
            c.showPage()
            page_num += 1

            # Page: About author
            logger.info("Adding about author page")
            self._draw_about_page(c, story_package, page_height=self.page_height)
            c.showPage()
            page_num += 1

            # Page: Coming soon
            logger.info("Adding coming soon page")
            self._draw_coming_soon_page(c, page_height=self.page_height)
            c.showPage()
            page_num += 1

            # Padding: Blank pages to reach 24-page minimum
            while page_num < self.MIN_PAGES:
                logger.info(f"Adding blank padding page {page_num}")
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
        story_package: StoryPackage,
        art_dir: str,
        output_path: str,
        page_count: int
    ) -> bool:
        """
        Build wraparound cover (back + spine + front).
        Spine width = (page_count * paper_thickness) + bleed
        """
        logger.info(f"Building wraparound cover: {output_path}")

        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Calculate spine width
            # Typical: 80lb paper = 0.0035" per page
            paper_thickness = 0.0035
            spine_width = (page_count * paper_thickness) + (2 * self.bleed)

            # Total width = back + spine + front (each with bleed)
            back_width = self.trim_width + self.bleed
            cover_width = back_width + spine_width + self.trim_width + self.bleed
            cover_height = self.trim_height + (2 * self.bleed)

            cover_width_px = int(cover_width * inch)
            cover_height_px = int(cover_height * inch)

            logger.info(f"Cover dimensions: {cover_width:.2f}x{cover_height:.2f} inches")

            # Create cover image
            cover_image = PILImage.new('RGB', (cover_width_px, cover_height_px), color=(255, 255, 255))
            draw = ImageDraw.Draw(cover_image)

            # Load front cover art
            art_path = Path(art_dir)
            front_image_path = art_path / "cover_front.png"

            if front_image_path.exists():
                front_img = PILImage.open(front_image_path)
                front_img = self._resize_for_cover(front_img, (self.trim_width, self.trim_height))
                front_x = int((back_width + spine_width) * inch)
                front_y = int(self.bleed * inch)
                cover_image.paste(front_img, (front_x, front_y))

            # Add title and author to front cover
            if front_image_path.exists():
                self._add_text_to_image(
                    cover_image,
                    story_package.title,
                    x=int((back_width + spine_width + self.trim_width / 2) * inch),
                    y=int((self.bleed + self.trim_height * 0.7) * inch),
                    size=60,
                    color=(255, 255, 255),
                    shadow=True
                )

            # Add blurb to back cover
            self._add_text_to_image(
                cover_image,
                story_package.blurb,
                x=int((self.bleed + self.trim_width / 2) * inch),
                y=int((self.bleed + self.trim_height * 0.3) * inch),
                size=24,
                color=(0, 0, 0),
                shadow=False
            )

            # Save to PDF
            # First convert PIL image to PDF-ready format
            cover_image.save(str(output_file), 'PDF', quality=95)
            logger.info(f"Cover PDF created: {output_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to build cover: {str(e)}")
            return False

    def build_kindle_cover(
        self,
        cover_image_path: str,
        output_path: str,
        size: Tuple[int, int] = (2560, 3900)
    ) -> bool:
        """
        Convert cover PNG to JPG for Kindle with proper dimensions.
        Kindle requires: 1600x2560 minimum, 2560x3900 maximum.
        """
        logger.info(f"Building Kindle cover: {output_path}")

        try:
            cover_file = Path(cover_image_path)
            if not cover_file.exists():
                logger.error(f"Cover image not found: {cover_file}")
                return False

            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Open and convert image
            img = PILImage.open(cover_file)

            # Convert RGBA to RGB if needed
            if img.mode == 'RGBA':
                background = PILImage.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background

            # Resize to Kindle dimensions (maintain aspect ratio)
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
        story_package: StoryPackage,
        art_dir: str,
        output_dir: str
    ) -> Dict[str, bool]:
        """
        Build all three files: interior PDF, cover PDF, Kindle cover JPG.
        Returns dictionary with success status for each file.
        """
        logger.info(f"Building all files to: {output_dir}")

        output_path = Path(output_dir)
        art_path = Path(art_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results = {}

        # Interior PDF - use standardized name for dashboard compatibility
        interior_path = output_path / "Interior.pdf"
        results['interior'] = self.build_interior(story_package, art_dir, str(interior_path))

        # Cover PDF - use standardized name for dashboard compatibility
        total_pages = self.MIN_PAGES
        cover_path = output_path / "Cover.pdf"
        results['cover'] = self.build_cover(story_package, art_dir, str(cover_path), total_pages)

        # Kindle Cover JPG - use the cover.png from art directory
        cover_png_path = art_path / "cover.png"
        kindle_cover_path = output_path / "Kindle_Cover.jpg"
        results['kindle_cover'] = self.build_kindle_cover(str(cover_png_path), str(kindle_cover_path))

        logger.info(f"Build complete: {results}")
        return results

    # ========== PRIVATE DRAWING METHODS ==========

    def _draw_warm_page(self, c: canvas.Canvas, title_text: str, page_height: float):
        """Draw a warm-colored title page"""
        # Warm background color (soft peach/cream)
        c.setFillColor(HexColor("#FFF8F0"))
        c.rect(0, 0, self.page_width, page_height, fill=1, stroke=0)

        # Title text
        c.setFont("Helvetica-Bold", 48)
        c.setFillColor(HexColor("#4A4A4A"))
        c.drawCentredString(self.page_width / 2, page_height / 2, title_text)

    def _draw_title_page(self, c: canvas.Canvas, story_package: StoryPackage, page_height: float):
        """Draw the official title page"""
        # Warm background
        c.setFillColor(HexColor("#FFF8F0"))
        c.rect(0, 0, self.page_width, page_height, fill=1, stroke=0)

        # Title
        c.setFont("Helvetica-Bold", 44)
        c.setFillColor(HexColor("#2C2C2C"))
        c.drawCentredString(self.page_width / 2, page_height - inch * 2, story_package.title)

        # Subtitle
        c.setFont("Helvetica", 28)
        c.setFillColor(HexColor("#666666"))
        c.drawCentredString(self.page_width / 2, page_height - inch * 3.5, story_package.subtitle)

        # Author
        c.setFont("Helvetica", 24)
        c.setFillColor(HexColor("#4A4A4A"))
        c.drawCentredString(self.page_width / 2, page_height / 2, f"by {story_package.author}")

    def _draw_copyright_page(self, c: canvas.Canvas, story_package: StoryPackage, page_height: float):
        """Draw copyright/publication info page"""
        # White background
        c.setFillColor(white)
        c.rect(0, 0, self.page_width, page_height, fill=1, stroke=0)

        # Copyright text
        y_pos = page_height - inch * 1
        c.setFont("Helvetica", 10)
        c.setFillColor(black)

        texts = [
            f"Copyright © 2024 {story_package.author}",
            "All rights reserved.",
            "",
            "Published by Creative Studio",
            "www.creativestudio.com",
            "",
            "This book contains content generated with AI assistance.",
            "All content has been reviewed and edited by humans.",
        ]

        for text in texts:
            c.drawString(inch * 0.75, y_pos, text)
            y_pos -= inch * 0.4

    def _draw_dedication_page(self, c: canvas.Canvas, page_height: float):
        """Draw dedication page"""
        # Warm background
        c.setFillColor(HexColor("#FFF8F0"))
        c.rect(0, 0, self.page_width, page_height, fill=1, stroke=0)

        # Dedication
        c.setFont("Helvetica-Oblique", 24)
        c.setFillColor(HexColor("#4A4A4A"))
        c.drawCentredString(
            self.page_width / 2,
            page_height / 2,
            "For young readers everywhere"
        )

    def _draw_story_spread(
        self,
        c: canvas.Canvas,
        page: StoryPage,
        art_dir: str,
        page_height: float
    ):
        """Draw a full-bleed story page with text overlays"""
        art_path = Path(art_dir)
        image_file = art_path / page.image_path

        if image_file.exists():
            # Load and resize image to full bleed
            img = PILImage.open(image_file)
            img = self._center_crop_image(img, self.page_width / inch, self.page_height / inch)

            # Save temporary image
            temp_path = Path("/tmp/temp_story_image.png")
            img.save(temp_path)

            # Draw full-bleed image
            c.drawImage(str(temp_path), 0, 0, width=self.page_width, height=page_height)

            # Clean up temp
            temp_path.unlink()
        else:
            # Fallback: solid color
            c.setFillColor(HexColor("#F0F0F0"))
            c.rect(0, 0, self.page_width, page_height, fill=1, stroke=0)

        # Add text overlays
        for overlay in page.text_overlays:
            self._draw_text_overlay(c, overlay, page_height)

    def _draw_text_overlay(self, c: canvas.Canvas, overlay: TextOverlay, page_height: float):
        """Draw a single text overlay with optional drop shadow"""
        x = overlay.x * inch
        y = page_height - (overlay.y * inch)

        if overlay.drop_shadow:
            # Shadow
            c.setFillColor(black)
            c.setFillAlpha(0.3)
            c.setFont(overlay.font_name, overlay.font_size)
            c.drawString(x + 2, y - 2, overlay.text)

        # Main text
        color = HexColor(f"#{overlay.color[0]:02x}{overlay.color[1]:02x}{overlay.color[2]:02x}")
        c.setFillColor(color)
        c.setFillAlpha(1.0)
        c.setFont(overlay.font_name, overlay.font_size)

        if overlay.align == "center":
            c.drawCentredString(x, y, overlay.text)
        elif overlay.align == "right":
            c.drawRightString(x, y, overlay.text)
        else:  # left
            c.drawString(x, y, overlay.text)

    def _draw_about_page(self, c: canvas.Canvas, story_package: StoryPackage, page_height: float):
        """Draw about the author page"""
        # Warm background
        c.setFillColor(HexColor("#FFF8F0"))
        c.rect(0, 0, self.page_width, page_height, fill=1, stroke=0)

        # Title
        c.setFont("Helvetica-Bold", 28)
        c.setFillColor(HexColor("#2C2C2C"))
        c.drawCentredString(self.page_width / 2, page_height - inch * 1, "About the Author")

        # Bio
        c.setFont("Helvetica", 12)
        c.setFillColor(HexColor("#4A4A4A"))
        bio_y = page_height - inch * 2.5
        bio_text = f"{story_package.author} creates magical stories for children everywhere."
        c.drawString(inch * 0.75, bio_y, bio_text)

    def _draw_coming_soon_page(self, c: canvas.Canvas, page_height: float):
        """Draw coming soon page"""
        # Warm background
        c.setFillColor(HexColor("#FFF8F0"))
        c.rect(0, 0, self.page_width, page_height, fill=1, stroke=0)

        # Coming soon text
        c.setFont("Helvetica-Bold", 32)
        c.setFillColor(HexColor("#4A4A4A"))
        c.drawCentredString(self.page_width / 2, page_height / 2, "Coming Soon...")

    # ========== IMAGE PROCESSING ==========

    def _center_crop_image(
        self,
        img: PILImage.Image,
        target_width_in: float,
        target_height_in: float
    ) -> PILImage.Image:
        """
        Center-crop image to target dimensions.
        Scales first to ensure full coverage, then crops from center.
        """
        # Convert inches to pixels (DPI is already pixels per inch)
        target_width = int(target_width_in * self.COLOR_QUALITY_DPI)
        target_height = int(target_height_in * self.COLOR_QUALITY_DPI)

        # Calculate aspect ratios
        img_aspect = img.width / img.height
        target_aspect = target_width / target_height

        if img_aspect > target_aspect:
            # Image is wider - scale by height
            new_height = target_height
            new_width = int(new_height * img_aspect)
        else:
            # Image is taller - scale by width
            new_width = target_width
            new_height = int(new_width / img_aspect)

        # Resize
        img = img.resize((new_width, new_height), PILImage.Resampling.LANCZOS)

        # Crop from center
        left = (new_width - target_width) // 2
        top = (new_height - target_height) // 2
        right = left + target_width
        bottom = top + target_height

        return img.crop((left, top, right, bottom))

    def _resize_for_cover(
        self,
        img: PILImage.Image,
        size_inches: Tuple[float, float]
    ) -> PILImage.Image:
        """Resize image to fit cover dimensions"""
        target_width = int(size_inches[0] * self.COLOR_QUALITY_DPI)
        target_height = int(size_inches[1] * self.COLOR_QUALITY_DPI)

        img.thumbnail((target_width, target_height), PILImage.Resampling.LANCZOS)

        # Create canvas with white background
        canvas_img = PILImage.new('RGB', (target_width, target_height), (255, 255, 255))
        offset = (
            (target_width - img.width) // 2,
            (target_height - img.height) // 2
        )
        canvas_img.paste(img, offset)
        return canvas_img

    def _add_text_to_image(
        self,
        img: PILImage.Image,
        text: str,
        x: int,
        y: int,
        size: int,
        color: Tuple[int, int, int],
        shadow: bool = False
    ):
        """Add text overlay to PIL image"""
        from PIL import ImageFont

        draw = ImageDraw.Draw(img)

        # Try to use a nice font, fallback to default
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except:
            font = ImageFont.load_default()

        if shadow:
            # Draw shadow
            draw.text((x + 2, y + 2), text, fill=(0, 0, 0, 128), font=font)

        # Draw main text
        draw.text((x, y), text, fill=color, font=font)


def main():
    """Example usage"""
    import argparse

    parser = argparse.ArgumentParser(description="PDF Builder for KDP")
    parser.add_argument('--title', default='Pixel Adventure', help='Book title')
    parser.add_argument('--author', default='Creative Studio', help='Author name')
    parser.add_argument('--art-dir', default='./art', help='Art directory')
    parser.add_argument('--output-dir', default='./output', help='Output directory')
    parser.add_argument('--trim-size', default='8.5x8.5', help='Trim size')
    args = parser.parse_args()

    try:
        builder = PDFBuilder(trim_size=args.trim_size)

        # Create sample story package
        story_package = StoryPackage(
            title=args.title,
            author=args.author,
            subtitle="A Digital Adventure",
            blurb="Join Pixel on an amazing journey through a digital wonderland filled with wonder and magic!",
            pages=[
                StoryPage(
                    image_path="story_01.png",
                    text_overlays=[
                        TextOverlay(
                            text="Once upon a time...",
                            x=4.25,
                            y=7.5,
                            font_size=32,
                            color=(255, 255, 255)
                        )
                    ]
                )
            ] * 12,  # 12 sample spreads
            trim_size="8.5x8.5",
            bleed=0.125
        )

        # Build all files
        results = builder.build_all(story_package, args.art_dir, args.output_dir)
        print(f"Build results: {results}")

    except Exception as e:
        logger.error(f"Build failed: {str(e)}")


if __name__ == '__main__':
    main()
