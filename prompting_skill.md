# OpenAI Image Generation: Character Consistency Mastery Guide

## Executive Summary

Achieving consistent character appearance across multiple AI-generated images remains one of the most challenging aspects of working with OpenAI's image generation models (gpt-image-1, gpt-image-1.5). While the models have significantly improved with gpt-image-1.5 offering robust facial and identity preservation, perfect pixel-identical replication is not possible since models do not retain memory between generations. Success depends on systematic prompting strategies, explicit constraints repeated in every prompt, and understanding that consistency must be enforced through careful prompt engineering rather than expected as a default behavior.

The key breakthrough insight from OpenAI's official guidance is the separation of "what should change" from "what must remain invariant" - and critically, restating those invariants on every single iteration to prevent drift. For children's book illustrations, this means creating a detailed character specification document upfront, then including the complete character description in every prompt while only varying the scene, pose, and action. The OpenAI Cookbook emphasizes a consistent prompt order: background/scene, then subject, then key details, then constraints. Following this structure while maintaining identical character description phrasing produces the best results.

The most effective technique combines three elements: (1) an "identity anchor" - a strong initial character description or reference image that serves as the foundation, (2) a "character DNA" prompt section that remains identical across all generations, and (3) explicit constraints that lock facial features, body proportions, skin tone, and clothing while only allowing specified elements to change. Using the `input_fidelity="high"` parameter when editing existing images significantly improves face and identity preservation. For new generations, the character sheet technique - generating multiple poses/angles in a single image first - provides a reference foundation for subsequent individual scene generation.

---

## Prompt Templates

### Template 1: Character Establishment (First Image)

```
[ART STYLE]: Children's book illustration in [watercolor/digital art/flat vector] style with [soft/vibrant] colors and [gentle/bold] lines.

[CHARACTER - IDENTITY ANCHOR]:
Name: [Character Name]
- Face: [specific face shape, e.g., round face with soft features]
- Eyes: [specific shape, size, color, e.g., large almond-shaped bright green eyes with long lashes]
- Nose: [specific description, e.g., small button nose]
- Skin: [specific tone using descriptive terms, e.g., warm honey-bronze skin]
- Hair: [color, length, style, texture, e.g., curly shoulder-length auburn hair with golden highlights]
- Body: [age, build, height relative to scene, e.g., 7-year-old girl with average build]
- Clothing: [detailed outfit, e.g., yellow rain boots, blue denim overalls over a red striped long-sleeve shirt]
- Distinguishing features: [any unique marks, accessories, e.g., small freckles across nose and cheeks, always wears a silver heart necklace]

[SCENE]: [Background/environment description]

[POSE/ACTION]: [What the character is doing]

[CONSTRAINTS]:
- Maintain exact character features as described above
- No text or watermarks
- No additional characters unless specified
- [Style] art style must remain consistent
```

### Template 2: Subsequent Scene Generation

```
[ART STYLE]: Children's book illustration in [SAME style as establishment image] style.

[CHARACTER - MUST PRESERVE EXACTLY]:
[Paste identical character description from Template 1]

[NEW SCENE]: [New background/environment]

[NEW POSE/ACTION]: [New action - the ONLY thing that changes]

[CONSTRAINTS]:
- CRITICAL: Preserve all character features exactly as established
- Change ONLY the scene and pose
- Keep identical: face shape, eye color/shape, nose, skin tone, hair color/style, body proportions, clothing
- Maintain consistent art style and color palette
- No text or watermarks
```

### Template 3: Character Sheet Generation

```
Create a character reference sheet showing the same character in multiple poses, arranged in a grid layout:

[CHARACTER DESCRIPTION]:
[Full character details]

[LAYOUT]: 4-panel grid arrangement showing:
- Top left: Front view, standing, neutral expression
- Top right: Side profile view (left side)
- Bottom left: 3/4 view, happy expression, waving
- Bottom right: Back view showing hair and clothing details

[CONSTRAINTS]:
- All panels must show the EXACT same character
- Consistent proportions across all views
- Uniform panel sizes with clear separation
- [Art style] consistent across all panels
- No background distractions - simple solid color backdrop
- No text labels
```

### Template 4: Multi-Character Scene

```
[ART STYLE]: [Consistent style description]

[CHARACTER 1 - IDENTITY ANCHOR]:
[Full description of first character - no internal commas]

[CHARACTER 2 - IDENTITY ANCHOR]:
[Full description of second character - no internal commas]

[SCENE]: [Environment description]

[CHARACTER POSITIONS]:
- [Character 1 name]: [position and pose]
- [Character 2 name]: [position and pose]

[INTERACTION]: [How characters are interacting]

[CONSTRAINTS]:
- Preserve exact features for both characters
- Maintain distinct visual separation between characters
- Consistent art style throughout
- [Additional constraints]
```

---

## Best Practices

### DO:

1. **Create a Character Bible first** - Before generating any images, write a comprehensive character description document that you will copy-paste into every prompt.

2. **Use identical phrasing** - When describing character features that must stay consistent, use the exact same words in the exact same order every time. "Large almond-shaped bright green eyes" should never become "big green almond eyes."

3. **Follow the prompt order** - Structure prompts as: Background/Scene → Subject/Character → Key Details → Constraints. This order is recommended by OpenAI's official cookbook.

4. **Include the intended use** - State "children's book illustration" to set the appropriate mode and style expectations.

5. **Specify art style explicitly** - Name the specific illustration style (watercolor, digital flat, gouache, etc.) and include it in every prompt.

6. **Use descriptive anchors for skin tones** - Instead of generic "brown skin," use specific descriptors like "warm honey-bronze," "deep espresso," "peachy cream," or "golden olive" for more consistent results.

7. **Lock invariants explicitly** - Include phrases like "maintain exact facial features," "preserve identical skin tone," "keep same hair style and color."

8. **Generate character sheets first** - Create a multi-angle reference image before generating individual scenes to establish the character visually.

9. **Use high input fidelity for edits** - When using the images.edit endpoint, set `input_fidelity="high"` to better preserve faces and identifying features.

10. **Keep clothing consistent** - Unless the story requires clothing changes, use identical clothing descriptions across all images.

11. **Repeat constraints on every iteration** - Never assume the model remembers previous instructions. Restate what must remain unchanged in every prompt.

12. **Place important features first** - Put the most critical consistency elements (face, distinctive features) early in the character description.

13. **Limit multi-pose generations to 4 images** - When generating multiple versions in one image, 4 is the sweet spot; more than 6 often causes consistency breakdown.

14. **Use line breaks for clarity** - Separate different aspects of your prompt (style, character, scene, constraints) with line breaks rather than running everything together.

### DON'T:

1. **Don't use internal commas in character descriptions** - Write "young girl with curly red hair wearing blue overalls" not "young girl, curly red hair, blue overalls." Commas can confuse which attributes belong to which element.

2. **Don't use "facing left" or "facing right"** - These phrases tend to rotate the entire image sideways. Instead use "looking toward the left side of the frame."

3. **Don't let the model rewrite your prompt** - DALL-E 3 sometimes modifies prompts. In ChatGPT, you can use "@DM" at the start with instructions not to modify your prompt.

4. **Don't expect pixel-perfect consistency** - The models will produce "recognizable similarity" but not identical replication. Accept slight variations.

5. **Don't use vague color descriptions** - Avoid "brownish" or "kind of green." Be specific: "chestnut brown," "emerald green."

6. **Don't change description phrasing between images** - Even synonyms can introduce drift. "Small nose" and "little nose" may produce different results.

7. **Don't overload with details** - Effective prompts are typically 15-50 words for the main description. Beyond that, prioritize ruthlessly.

8. **Don't forget age-appropriate proportions** - Children have different body proportions than adults. Specify age and let that guide proportions naturally.

9. **Don't skip the art style specification** - Without explicit style guidance, the model may drift between styles across generations.

10. **Don't assume the model remembers previous images** - Every generation starts fresh. Include all relevant information every time.

---

## Character Description Format

### The Optimal Character Description Structure

```
[NAME] is a [age] [gender/identity] with:

FACE:
- Shape: [round/oval/square/heart-shaped]
- Expression tendency: [typically cheerful/serious/curious]

EYES:
- Shape: [almond/round/hooded/wide-set]
- Size: [large/medium/small] relative to face
- Color: [specific shade, e.g., "deep sapphire blue with gold flecks"]
- Notable features: [long lashes/glasses/etc.]

NOSE:
- Shape and size: [button/aquiline/upturned/straight]

SKIN:
- Tone: [use descriptive terms: honey-bronze, warm sienna, peachy cream, deep mahogany, golden olive, porcelain]
- Notable features: [freckles/dimples/birthmarks with specific locations]

HAIR:
- Color: [be specific: auburn with copper highlights, jet black with blue sheen]
- Length: [in relation to body: shoulder-length, chin-length, waist-length]
- Style: [curly/straight/wavy/braided/in pigtails]
- Texture: [fine/thick/coarse]

BODY:
- Build: [thin/average/stocky for age]
- Height: [tall/average/short for age]
- Notable posture: [energetic/slouchy/proper]

CLOTHING (Default Outfit):
- Top: [specific item with color and details]
- Bottom: [specific item with color and details]
- Footwear: [specific with color]
- Accessories: [items always present]

DISTINGUISHING FEATURES:
- [Unique elements that make this character recognizable]
- [Signature items or traits]
```

### Example Character Description

```
MAYA is a 6-year-old girl with:

FACE:
- Shape: Round face with soft, childlike features
- Expression tendency: Bright and curious

EYES:
- Shape: Large, wide-set almond eyes
- Size: Prominently large (characteristic of children's book style)
- Color: Warm chocolate brown with golden undertones
- Notable features: Long dark lashes, eyes that sparkle with wonder

NOSE:
- Shape and size: Small button nose with a slight upturn

SKIN:
- Tone: Warm caramel brown with golden undertones
- Notable features: Small beauty mark on left cheek, rosy cheeks when excited

HAIR:
- Color: Deep black with subtle brown highlights in sunlight
- Length: Shoulder-length
- Style: Natural curly texture, usually worn in two puff balls with colorful hair ties
- Texture: Thick and springy curls

BODY:
- Build: Average healthy build for a 6-year-old
- Height: Average for age
- Notable posture: Energetic, often leaning forward with curiosity

CLOTHING (Default Outfit):
- Top: Bright sunflower-yellow t-shirt with a small rainbow on the chest
- Bottom: Purple corduroy overalls with silver star-shaped buttons
- Footwear: Red canvas sneakers with white laces and white toe caps
- Accessories: Always wears her grandmother's small silver butterfly pendant

DISTINGUISHING FEATURES:
- The two curly puff balls in her hair (signature look)
- The silver butterfly pendant (never removed)
- Tends to have one overall strap slightly falling off shoulder
```

---

## Common Pitfalls

### 1. The Drift Problem
**What happens:** Character features gradually shift across images - hair gets longer, eyes change color, face shape morphs.
**Why it happens:** The model has no memory between generations and interprets each prompt independently.
**Solution:** Copy-paste the identical character description into every prompt. Never paraphrase or summarize.

### 2. The Synonym Trap
**What happens:** Using "small nose" in one prompt and "little nose" in another produces noticeably different results.
**Why it happens:** Different words activate different associations in the model's training data.
**Solution:** Create a character template and use copy-paste, never retyping or rewording.

### 3. The Art Style Slide
**What happens:** First image is watercolor, third image looks like digital vector art.
**Why it happens:** Art style wasn't explicitly constrained in every prompt.
**Solution:** Include identical art style specification in every prompt, including specific descriptors like "soft watercolor washes," "visible brush strokes," "gentle color bleeding."

### 4. The Proportion Problem
**What happens:** Character appears as different ages across images - childlike in one, more mature in another.
**Why it happens:** Body proportions weren't explicitly specified.
**Solution:** State age clearly and include proportion guidance: "typical proportions of a 6-year-old child with a larger head-to-body ratio."

### 5. The Accessory Amnesia
**What happens:** Character's signature items (glasses, necklace, hair bow) appear and disappear.
**Why it happens:** Accessories weren't included in the core character description.
**Solution:** List signature accessories as "ALWAYS present" items in the character description.

### 6. The Background Bleed
**What happens:** Background elements start influencing character appearance (blue sky makes eyes bluer).
**Why it happens:** The model sometimes allows environmental colors to affect character rendering.
**Solution:** Explicitly separate character colors from environment: "Maya's warm chocolate brown eyes (distinct from the blue sky background)."

### 7. The Comma Confusion
**What happens:** Attributes get mixed up between characters or elements.
**Why it happens:** Commas in descriptions create ambiguous attribute boundaries.
**Solution:** Use continuous phrases without internal commas for each character block.

### 8. The Left-Right Flip
**What happens:** Entire image appears rotated or mirrored unexpectedly.
**Why it happens:** Terms like "facing left" or "facing right" are interpreted as image rotation instructions.
**Solution:** Use "looking toward the left side of the frame" or "body angled to the right."

### 9. The Over-Specification Paradox
**What happens:** Extremely detailed prompts produce worse results than moderate ones.
**Why it happens:** Conflicting details or information overload causes the model to make arbitrary choices.
**Solution:** Keep character descriptions to essential, distinctive features. Quality over quantity.

### 10. The First-Image Anchor Missing
**What happens:** No consistent baseline exists for character appearance.
**Why it happens:** Started generating scenes without establishing character appearance first.
**Solution:** Always generate a character reference sheet or establishment image before scene work.

---

## Example Prompts

### Example 1: Poor Prompt (Before)

```
Draw a picture of a little girl named Maya in a garden. She has curly hair and brown eyes. She's picking flowers. Make it look like a children's book.
```

**Problems:**
- Vague art style ("like a children's book")
- Minimal character details
- No constraints
- No specific colors
- Won't produce consistency across multiple images

### Example 1: Improved Prompt (After)

```
Children's book illustration in soft watercolor style with gentle color washes and visible brush texture.

CHARACTER - MAYA (must preserve exactly):
A 6-year-old African American girl with a round face and warm caramel-brown skin. Large wide-set almond-shaped chocolate brown eyes with long dark lashes. Small upturned button nose. Thick black curly hair worn in two puff balls secured with bright pink hair ties. Wearing sunflower-yellow t-shirt under purple corduroy overalls with silver star buttons. Red canvas sneakers with white laces. Small silver butterfly pendant necklace.

SCENE: A sunny cottage garden with colorful wildflowers in soft pinks, purples, and yellows. White picket fence in background. Warm golden afternoon lighting.

ACTION: Maya is kneeling in the garden, carefully picking a bright purple flower, looking at it with wonder and delight. Gentle smile on her face.

CONSTRAINTS:
- Maintain all character features exactly as described
- Soft watercolor style throughout
- Warm, cheerful color palette
- No text or watermarks
- Character should be the clear focal point
```

---

### Example 2: Poor Multi-Character Prompt (Before)

```
Two kids, a boy and a girl, playing in a treehouse. The boy has red hair and the girl has braids. Children's book style.
```

**Problems:**
- Characters will be unrecognizable in subsequent images
- No specific details for consistency
- Art style not specified adequately

### Example 2: Improved Multi-Character Prompt (After)

```
Children's book illustration in warm gouache painting style with rich colors and soft edges.

CHARACTER 1 - OLIVER:
An 8-year-old boy with fair peachy-cream skin and a spray of orange freckles across his nose and cheeks. Bright copper-red straight hair in a messy short cut that sticks up at the crown. Round face with large curious hazel-green eyes. Small ears that stick out slightly. Wearing a forest-green hoodie with the hood down, khaki cargo shorts, and scuffed brown hiking boots. Always has a magnifying glass hanging from a cord around his neck.

CHARACTER 2 - AMARA:
A 7-year-old girl with deep mahogany-brown skin and warm undertones. Dark brown eyes that are large and expressive with a slight upward tilt at the corners. Oval face with high cheekbones. Black hair styled in neat cornrow braids gathered into two low buns at the back. Wearing a coral-pink t-shirt with a small embroidered bee on the pocket, denim shorts with rolled cuffs, and bright turquoise jelly sandals. Yellow friendship bracelet on her right wrist.

SCENE: A cozy wooden treehouse interior with sunlight streaming through a round window. Wooden plank walls with drawings tacked up. A small table with books and a jar of collected leaves.

POSITIONS AND ACTION:
- Oliver: Sitting cross-legged on the floor, holding his magnifying glass up to examine a large oak leaf
- Amara: Sitting across from him, leaning forward with excitement, pointing at something on the leaf

CONSTRAINTS:
- Both characters must match their descriptions exactly
- Warm gouache painting style consistent throughout
- Maintain distinct visual separation between characters
- Warm afternoon lighting from window
- No text or watermarks
```

---

### Example 3: Scene Continuation (Keeping Character Consistent)

**Original Scene Prompt:**
```
[Initial Maya garden scene as shown in Example 1 - AFTER version]
```

**Continuation Scene - Different Setting:**

```
Children's book illustration in soft watercolor style with gentle color washes and visible brush texture. [IDENTICAL STYLE]

CHARACTER - MAYA (must preserve exactly from previous images):
A 6-year-old African American girl with a round face and warm caramel-brown skin. Large wide-set almond-shaped chocolate brown eyes with long dark lashes. Small upturned button nose. Thick black curly hair worn in two puff balls secured with bright pink hair ties. Wearing sunflower-yellow t-shirt under purple corduroy overalls with silver star buttons. Red canvas sneakers with white laces. Small silver butterfly pendant necklace.
[IDENTICAL CHARACTER - copy-pasted exactly]

NEW SCENE: Maya's cozy bedroom at dusk. Lavender walls with a window showing a pink and orange sunset. A small wooden bed with a patchwork quilt in purples and yellows. A bookshelf with colorful books. Soft warm lamp light mixing with sunset glow.

NEW ACTION: Maya is sitting on her bed holding the purple flower from the garden, now in a small glass jar of water. She's looking at it with a gentle, happy smile, the butterfly pendant visible at her collar.

CONSTRAINTS:
- CRITICAL: Character must be identical to garden scene - same face, same skin tone, same hair, same outfit
- Change ONLY the scene and pose
- Watercolor style must match previous image
- Warm evening color palette
- No text or watermarks
```

---

## Technical Notes

### API Parameters for Consistency

#### Model Selection
- **gpt-image-1.5** - Best overall quality and consistency; recommended for production work
- **gpt-image-1** - Good quality, slightly lower cost
- **gpt-image-1-mini** - Cost-effective but lower fidelity; not recommended for character consistency work
- **dall-e-3** and **dall-e-2** - Deprecated as of May 12, 2026

#### Key Parameters

| Parameter | Values | Recommendation for Consistency |
|-----------|--------|-------------------------------|
| `model` | gpt-image-1.5, gpt-image-1, gpt-image-1-mini | Use gpt-image-1.5 for best results |
| `quality` | low, medium, high | Use "high" for character work |
| `size` | 1024x1024, 1536x1024, 1024x1536, auto | Use consistent size across project |
| `input_fidelity` | low, high | Use "high" when editing images with faces |
| `output_format` | png, webp, jpeg | PNG for editing workflow; JPEG for final |

#### Using `input_fidelity` for Edits

When using the `images.edit` endpoint to modify existing character images:

```python
response = client.images.edit(
    model="gpt-image-1.5",
    image=open("character_base.png", "rb"),
    mask=open("mask.png", "rb"),
    prompt="[Your edit prompt]",
    input_fidelity="high"  # Critical for face preservation
)
```

**Important:** With `input_fidelity="high"`:
- Faces are preserved far more accurately
- Use when characters need to remain recognizable across edits
- Consumes more image input tokens
- If using multiple images with gpt-image-1, place the image with faces FIRST

#### Mask Behavior Note

The `images.edit` endpoint with GPT image models does not do pixel-perfect mask replacement like DALL-E 2 did. It uses a "soft mask" approach with total image recreation. For best results:
- Keep masks for small areas
- Explicitly state what must NOT change in the prompt
- Use `input_fidelity="high"` to preserve surrounding areas

### Consistency Across a Book Project

#### Recommended Workflow

1. **Pre-Production**
   - Write complete Character Bible with all descriptions
   - Define art style precisely (save as template text)
   - Create color palette reference

2. **Character Establishment Phase**
   - Generate character sheet (4-panel grid) for each main character
   - Review and select best representation
   - Save selected image as reference

3. **Scene Generation Phase**
   - Copy-paste character description for EVERY prompt
   - Use identical art style text for EVERY prompt
   - Only vary: scene/background, pose/action
   - Generate 2-3 variations per scene, select best

4. **Quality Control**
   - Compare each new image to character sheet
   - Check: face shape, eye color, skin tone, hair style, clothing, accessories
   - Regenerate any images with noticeable drift

5. **Post-Processing**
   - Minor color correction for consistency
   - Ensure lighting temperature matches across spreads

### Seeds and Gen IDs

**Seed Numbers:**
- DALL-E 3 supports seed numbers for reproducibility
- Using the same seed + same prompt produces the same image
- Useful for recreating a specific result

**Gen IDs:**
- After generating an image, you can request its Gen ID
- Gen ID captures the specific style and details as a "fingerprint"
- Use Gen ID in subsequent prompts to maintain style consistency
- Particularly useful for style transfer and maintaining visual language

### Token Considerations

- High-quality character images with detailed prompts consume more tokens
- `input_fidelity="high"` increases token usage
- Budget for 2-3 generation attempts per scene
- Character sheet generation is a worthwhile upfront investment

---

## Quick Reference Card

### The 5 Essentials for Every Prompt

1. **Art Style** - Identical text every time
2. **Character Block** - Copy-pasted exactly, never rewritten
3. **Scene Description** - The variable element
4. **Action/Pose** - The other variable element
5. **Constraints** - Always include "preserve character features"

### Character Description Checklist

- [ ] Face shape specified
- [ ] Eye shape, size, AND color
- [ ] Nose shape
- [ ] Skin tone (descriptive, not generic)
- [ ] Hair color, length, style, texture
- [ ] Age stated
- [ ] Body build/proportions for age
- [ ] Complete outfit with colors
- [ ] Distinguishing features/accessories
- [ ] Personality hint for expression tendency

### Red Flags - If You See These, Regenerate

- Eye color has shifted
- Skin tone is noticeably different
- Hair length or style changed
- Signature accessories missing
- Face shape looks different (rounder/longer)
- Art style feels different
- Character looks older/younger

---

## Sources and References

- [OpenAI Image Generation Documentation](https://platform.openai.com/docs/guides/image-generation)
- [GPT-Image-1.5 Prompting Guide - OpenAI Cookbook](https://cookbook.openai.com/examples/multimodal/image-gen-1.5-prompting_guide)
- [Generate Images with High Input Fidelity - OpenAI Cookbook](https://cookbook.openai.com/examples/generate_images_with_high_input_fidelity)
- [OpenAI API Reference - Images](https://platform.openai.com/docs/api-reference/images)
- [OpenAI Developer Community Forums](https://community.openai.com/)
- [How to Create Consistent Characters with DALL-E 3 - Medium](https://medium.com/@shailesh.7890/how-to-create-consistent-characters-with-dall-e-3-617216786408)
- [99% Character Consistency with DALL-E 3 - MyAIForce](https://myaiforce.com/dalle-3-character-consistency/)
- [Character Consistency in Generative AI - Skywork AI](https://skywork.ai/blog/character-consistency-generative-ai/)
- [AI Cartoon Character Prompting Guide - Neolemon](https://www.neolemon.com/blog/ai-cartoon-character-prompting-guide/)
- [Maintaining Consistency in AI Image Generation - AI Studios](https://www.aistudios.com/how-to-guides/maintaining-consistency-in-ai-image-generation-prompt-design-strategies-for-professionals)

---

*Last Updated: March 2026*
*For use with OpenAI gpt-image-1 and gpt-image-1.5 models*
