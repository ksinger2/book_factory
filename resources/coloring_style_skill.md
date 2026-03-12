# Coloring Book Style Generation Skill

## Overview
This skill guides the generation of coloring book reference/style sheets that establish consistent line weights, complexity levels, and visual language for an entire coloring book.

---

## Age Level Specifications

### Kid (Ages 3-6)
- **Line Weight**: 4-6pt thick bold lines
- **Complexity**: 3-8 planes per object (very simple shapes)
- **Coloring Areas**: Extra large, easy to stay inside
- **Content**: Simple animals, basic objects, cartoon characters
- **Details**: Minimal - no fine patterns or small elements

### Tween (Ages 7-12)
- **Line Weight**: 2-4pt medium lines
- **Complexity**: 10-20 planes per object
- **Coloring Areas**: Medium sized, some smaller sections
- **Content**: Characters, simple scenes, beginner patterns
- **Details**: Moderate - some decorative elements allowed

### Teen (Ages 13-17)
- **Line Weight**: 1-2pt finer lines
- **Complexity**: 20-40 planes per object
- **Coloring Areas**: Varied sizes including smaller sections
- **Content**: Fantasy, anime-style, detailed characters
- **Details**: Intricate - patterns and fine details

### YA (Young Adult 18-25)
- **Line Weight**: 0.5-1.5pt fine detailed lines
- **Complexity**: 30-50 planes per object
- **Coloring Areas**: Mix of large and detailed small areas
- **Content**: Artistic, trendy themes, sophisticated designs
- **Details**: High - fine patterns and elaborate elements

### Adult (Ages 26-55)
- **Line Weight**: 0.25-1pt very fine intricate lines
- **Complexity**: 40-80+ planes per object
- **Coloring Areas**: Many small detailed sections
- **Content**: Mandalas, botanicals, architecture, complex patterns
- **Details**: Maximum - extremely intricate designs

### Elder (Ages 55+)
- **Line Weight**: 1.5-3pt medium-bold clear lines
- **Complexity**: 15-30 planes per object
- **Coloring Areas**: Larger, well-defined areas
- **Content**: Nostalgic themes, nature, relaxing scenes
- **Details**: Moderate - clear shapes with some detail

---

## Difficulty Modifiers

Apply these adjustments to the base age level specifications:

### Easy
- Reduce plane count by 50%
- Widen all coloring areas
- Thicken line weights by 1pt
- Remove fine details and small elements

### Medium
- Standard specifications for age level
- No modifications needed

### Hard
- Increase plane count by 50%
- Add fine detail patterns within larger areas
- Thin line weights by 0.5pt
- Include more decorative elements

### Expert
- Double the plane count
- Maximum intricacy within age-appropriateness
- Finest lines appropriate for age level
- Every area has sub-patterns

---

## Theme-Specific Guidelines

### Mandalas & Patterns
- Circular symmetry is essential
- Repeat patterns radiating from center
- Consistent spacing between elements
- Balance complexity from center to edge
- Include both organic and geometric shapes

### Animals & Pets
- Clear animal silhouettes
- Fur/feather texture through line patterns
- Expressive but simple facial features
- Consider the animal's natural patterns
- Background can be minimal or themed

### Nature & Botanicals
- Organic flowing lines
- Leaf veins and petal details as lines
- Consider seasonal elements
- Layer flowers, leaves, stems naturally
- Include insects or small creatures optionally

### Fantasy & Mythology
- Dramatic poses and compositions
- Mix geometric and organic elements
- Include magical effects (stars, swirls, flames)
- Detailed costume/armor elements
- Background storytelling elements

### Aquatic & Ocean
- Flowing wave patterns
- Scale patterns for fish
- Coral and seaweed textures
- Bubbles as simple circles
- Underwater lighting effects through lines

### Architecture & Cities
- Precise geometric lines
- Perspective accuracy
- Brick/stone texture patterns
- Window and door details
- Surrounding landscape elements

---

## Reference Sheet Prompt Template

```
Generate a COLORING BOOK REFERENCE SHEET showing the unified visual style for this book.

BOOK SPECIFICATIONS:
- Theme: {theme}
- Age Level: {age_level}
- Difficulty: {difficulty}
- Line Weight: {line_weight_spec}
- Complexity: {planes_per_object} planes per object

REFERENCE SHEET LAYOUT:
Display 4-6 example elements arranged on a clean white background:
1. Main subject/character in the theme
2. Secondary element (supporting object or creature)
3. Border or frame pattern sample
4. Background texture or fill pattern
5. Decorative element (optional)
6. Small detail element (optional)

CRITICAL STYLE REQUIREMENTS:
- PURE BLACK LINES on WHITE background ONLY
- NO colors, gradients, shading, or gray tones
- ALL shapes must be CLOSED (no open-ended lines)
- Line weight: {line_weight_spec} consistently throughout
- Clean intersections where lines meet
- Even spacing in repeating patterns
- NO text, labels, or watermarks

QUALITY STANDARDS:
- Lines must be crisp and clear
- No jagged edges or pixelation
- No breaks or gaps in lines
- Symmetry where design requires it
- Print-ready quality at 300 DPI
```

---

## QA Checklist for Reference Sheets

1. **Line Quality**
   - [ ] Consistent line weight throughout
   - [ ] Clean, crisp lines (no jaggies)
   - [ ] No broken or incomplete lines

2. **Color Check**
   - [ ] Pure black lines only
   - [ ] Pure white background only
   - [ ] No gray tones or gradients
   - [ ] No accidental color

3. **Closure Check**
   - [ ] All shapes fully closed
   - [ ] No open-ended lines
   - [ ] No gaps that would allow color bleeding

4. **Age Appropriateness**
   - [ ] Complexity matches age level
   - [ ] Line weight appropriate for motor skills
   - [ ] Content suitable for audience

5. **Theme Consistency**
   - [ ] Elements match chosen theme
   - [ ] Unified visual language
   - [ ] Style consistent across all elements

---

## Common Issues to Avoid

### Generation Issues
- **Gray shading**: Explicitly state "NO shading, NO gray tones"
- **Open lines**: Emphasize "ALL shapes must be CLOSED"
- **Text appearing**: State "NO text, NO labels, NO writing"
- **Color bleeding in**: Specify "Pure black and white only"
- **Inconsistent style**: Show multiple examples in reference sheet

### Design Issues
- **Too complex for age**: Always state age level explicitly
- **Unbalanced composition**: Request "balanced" or "centered" layout
- **Boring/repetitive**: Ask for "variety within unified style"
- **Unclear focal point**: Specify primary element

---

## Example Prompts by Theme

### Mandala (Adult, Hard)
```
Generate a coloring book reference sheet for an intricate mandala design.

STYLE: Adult coloring book, hard difficulty
- Very fine 0.5pt black lines on white
- 60-80 planes per mandala section
- Complex interlocking patterns
- Zentangle-inspired fill patterns

Show: Central medallion, border pattern, corner element, fill texture samples
Pure black lines only, no color, all shapes closed, print-ready quality.
```

### Animals (Kid, Easy)
```
Generate a coloring book reference sheet for cute farm animals.

STYLE: Children ages 3-6, easy difficulty
- Bold 5pt black lines on white
- 4-6 planes per animal (very simple)
- Large open coloring areas
- Friendly cartoon style

Show: One cow, one pig, one chicken, simple fence, flower
Pure black lines only, no color, all shapes closed, extra thick outlines.
```

### Fantasy Dragons (Teen, Medium)
```
Generate a coloring book reference sheet for fantasy dragons.

STYLE: Teen ages 13-17, medium difficulty
- 1.5pt black lines on white
- 25-35 planes per dragon section
- Detailed scales and wing patterns
- Dynamic poses

Show: Dragon head, wing detail, tail section, flame element, treasure piece
Pure black lines only, no color, all shapes closed, anime-influenced style.
```
