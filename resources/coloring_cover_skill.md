# Coloring Book Cover Generation Skill

## Overview
This skill guides the generation of compelling, professional coloring book covers that drive sales on Amazon KDP. Covers must show colored sample art to demonstrate the book's content while maintaining commercial appeal.

---

## Cover Design Principles

### Age-Based Background Rules

| Age Level | Background | Color Scheme | Sample Presentation |
|-----------|------------|--------------|---------------------|
| Kid (3-6) | White/light/pastel | Bright, primary colors | 1-2 fully colored characters, playful |
| Tween (7-12) | White or soft color | Vibrant, fun colors | 2-3 colored elements, energetic |
| Teen (13-17) | Can be colored | Trendy, bold palette | Partially colored with BW sections |
| YA (18-25) | Dark or sophisticated | Aesthetic, Instagram-worthy | Mix of colored and line art |
| Adult (26-55) | Dark/black preferred | Rich, jewel tones | Single colored piece on dark bg |
| Elder (55+) | Soft, calming color | Muted, peaceful tones | Fully colored, welcoming |

### Essential Cover Elements

1. **Title**: Large, readable at thumbnail size (100px)
2. **Colored Sample**: 1-2 fully colored pages from inside the book
3. **Theme Indicator**: Visual cue to book's content
4. **Author/Brand**: Subtle but present
5. **Age Indicator**: "For Adults" / "For Kids" if appropriate

---

## Title Typography Guidelines

### Size & Placement
- Title should occupy 25-40% of cover width
- Must be readable at Amazon thumbnail size (160px wide)
- Place in top third OR bottom third (not middle)
- Leave breathing room around title

### Font Recommendations by Theme
- **Mandalas**: Elegant serif or decorative script
- **Animals**: Playful, rounded sans-serif
- **Nature**: Organic, flowing fonts
- **Fantasy**: Medieval or decorative display
- **Kids**: Bold, bubbly, fun fonts

### Color Contrast
- Dark background → White or bright text with glow
- Light background → Dark text with subtle shadow
- Ensure high contrast ratio (4.5:1 minimum)

---

## Colored Sample Strategies

### Single Hero Image
Best for: Adult books, intricate designs
- One stunning colored piece, 60-80% of cover
- Shows the book's best work
- High impact, professional look

### Collage/Mosaic
Best for: Variety themes, kids books
- 3-4 smaller colored samples
- Shows range of content
- More playful, less serious

### Partial Color
Best for: Teen/YA, artistic feel
- Line art with some colored sections
- Creates intrigue
- Modern, trendy look

### Before/After Split
Best for: Marketing the experience
- Half colored, half line art
- Shows transformation
- Demonstrates value

---

## Cover Prompt Template

```
Generate a COLORING BOOK COVER for KDP publishing.

BOOK DETAILS:
- Title: {title}
- Theme: {theme}
- Age Level: {age_level}
- Difficulty: {difficulty}

COVER SPECIFICATIONS:
- Dimensions: 2560 x 1600 pixels (Kindle) or 8.5 x 8.5 inches with bleed (Print)
- Background: {background_color_based_on_age}
- Style: Professional, commercial, Amazon-ready

LAYOUT:
- Title "{title}" prominently displayed
- {colored_sample_strategy} colored sample artwork
- Theme: {theme} clearly represented
- Age-appropriate design language

COLORED SAMPLE REQUIREMENTS:
- Show {1-3} fully colored example(s) from the book
- Colors should be: {color_palette_for_age}
- Demonstrate the {difficulty} difficulty level
- Make the coloring quality aspirational

TITLE TYPOGRAPHY:
- Font style: {font_recommendation_for_theme}
- Must be readable at 100px width (thumbnail size)
- High contrast with background
- {glow_or_shadow} for visibility

PROFESSIONAL STANDARDS:
- Clean, polished, commercial look
- No copyright-infringing elements
- No excessive text (title + subtitle max)
- Print-ready at 300 DPI
```

---

## Back Cover Guidelines

### Purpose
- Reinforce the book's value
- Show more sample content
- Include marketing copy space
- Professional presentation

### Layout Elements
1. **Blurb Space**: Top 40% reserved for text overlay
2. **Preview Images**: 2-3 small sample pages
3. **Features List**: "48 pages" / "Single-sided printing"
4. **Barcode Area**: Bottom right, 2" x 1.5" clear space

### Back Cover Prompt Template
```
Generate a COLORING BOOK BACK COVER for KDP publishing.

BOOK DETAILS:
- Title: {title}
- Theme: {theme}
- Age Level: {age_level}

BACK COVER SPECIFICATIONS:
- Dimensions: Match front cover with spine allowance
- Background: Complementary to front cover
- Style: Professional, commercial

LAYOUT:
- Top 40%: Clean space for text overlay (blurb)
- Middle: 2-3 small preview images of colored pages
- Bottom right: Clear 2" x 1.5" space for barcode

SAMPLE IMAGES:
- Small thumbnails showing variety
- Mix of colored and line art acceptable
- Demonstrate range of difficulty

DO NOT INCLUDE:
- Actual text (will be overlaid separately)
- Barcode graphics
- Price information
```

---

## Theme-Specific Cover Examples

### Mandala (Adult)
```
Cover: Dark navy/black background
Sample: Single large mandala, colored in jewel tones (emerald, ruby, sapphire)
Title: Elegant gold script font, centered
Accent: Subtle gold line border
```

### Animals (Kids)
```
Cover: Bright white or soft yellow background
Sample: 2-3 cute animals colored in primary colors
Title: Big, bubbly, rainbow letters
Accent: Stars, hearts, or paw prints scattered
```

### Fantasy Dragons (Teen)
```
Cover: Deep purple gradient background
Sample: One dramatic dragon, colored in fire colors
Title: Medieval-style font, silver with flame glow
Accent: Celtic knot border element
```

### Nature Botanicals (Elder)
```
Cover: Soft sage green background
Sample: Elegant flower arrangement, watercolor-style colors
Title: Classic serif, dark green
Accent: Delicate vine border
```

---

## Amazon Thumbnail Optimization

### The 160px Test
Your cover must work at 160px wide (Amazon search results).

**Checklist:**
- [ ] Title readable at thumbnail size
- [ ] Main visual element clear
- [ ] Colors pop and differentiate from competitors
- [ ] No small details lost
- [ ] Vertical orientation feels balanced

### Color Psychology for Sales
- **Red/Orange**: Energy, excitement, action
- **Blue/Green**: Calm, relaxation, nature
- **Purple**: Luxury, creativity, mystical
- **Yellow**: Joy, happiness, kids
- **Black**: Sophistication, adult, premium
- **White**: Clean, simple, modern

---

## Quality Checklist

### Pre-Generation
- [ ] Age level background color selected
- [ ] Colored sample strategy chosen
- [ ] Title font style determined
- [ ] Color palette approved

### Post-Generation
- [ ] Title is readable at thumbnail size
- [ ] Colored samples look professional
- [ ] Background is appropriate for age
- [ ] No artifacts or generation errors
- [ ] Professional commercial quality
- [ ] Dimensions correct for format

### Common Issues
- **Title too small**: Regenerate with "LARGE readable title" emphasis
- **Colors muddy**: Specify "vibrant" or "saturated" colors
- **Busy/cluttered**: Simplify layout, reduce elements
- **Not commercial**: Add "professional Amazon KDP quality"
