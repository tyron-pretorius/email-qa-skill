# Email Rendering QA Checklist

> Research sources: Mailosaur (March 2026), DEV Community / Mailpeek (Feb 2026), Litmus Dark Mode Guide, caniemail.com scoreboard.
> This checklist is used by subagents visually inspecting Email on Acid screenshots. Every client must be checked — do not sample.

---

## How to review a screenshot

For each client, work through the sections below in order. Report every issue found, not just the first one. Be specific: name the element that's broken, describe what it looks like vs. what it should look like, and rate severity (FAIL = broken/unreadable, WARN = degraded but functional).

---

## 1. Layout

Check for:
- **Broken columns** — side-by-side sections stacking vertically when they shouldn't (common in Outlook Word engine when `max-width`/`display:flex` is ignored)
- **Content overflow** — text or images extending beyond the email container, causing horizontal scroll
- **Giant unexplained gaps** — blank vertical space caused by ignored `padding`/`margin` on `<div>` elements (Outlook) or `height` converted to `min-height` (Yahoo)
- **Collapsed sections** — a block that should have height/padding has collapsed to nothing
- **Container width** — on desktop clients, the email should sit centred at roughly 600px, not stretched full width

---

## 2. Text and typography

Check for:
- **Clipped or truncated copy** — text cut off at the edge of a container
- **Overlapping text** — two text elements rendered on top of each other
- **Font fallback issues** — in Outlook (Word engine), web fonts fall back to **Times New Roman** (not the next font in the stack). This changes line length, wrapping, and overall layout significantly. Flag if the font looks obviously serif/wrong.
- **Widowed CTAs** — a call-to-action phrase that wraps onto its own orphaned line due to fallback font reflow
- **Text size on mobile** — body text should be at least 14px, headlines legible without zooming. Flag anything that looks uncomfortably small.
- **Line height/spacing** — inconsistent spacing between paragraphs that looks unintentional

---

## 3. Images

Check for:
- **Broken image icons** — the classic broken-image placeholder, indicating the image URL failed to load
- **Missing background images** — sections with a background-image in CSS will be blank in Outlook (Word engine) unless a VML fallback is in place. Flag as FAIL if a section appears to be missing its background.
- **Retina/scaling issues** — images appearing blurry on high-DPI screens (images should be 2× their display size)
- **Images blocked** — some clients show the email with images off by default. Check if the alt text fills in meaningfully or if large blank gaps appear.
- **Image width overflow** — images extending beyond the email container (especially on Samsung Mail, which uses the HTML `width` attribute to set viewport width)

---

## 4. Buttons and CTAs

Check for:
- **Button not visible** — entirely absent or invisible against the background
- **Button cut off** — button text or border clipped at the edge
- **Padding collapsed** — button looks like plain underlined text with no pill/box shape (common in Outlook when `border-radius` and `padding` are ignored on `<a>` tags)
- **CTA low-contrast** — button text and background colour are too similar to read (especially in dark mode)
- **Tap target too small** — on mobile, buttons should be at least 44×44px. A thin text link as the only CTA is a usability failure on touch devices.

---

## 5. Mobile-specific checks

Check for:
- **Content cut off at viewport edge** — text or images touching or crossing the right edge of a mobile screen
- **Font size too small** — text that requires pinch-zoom to read
- **Tap targets** — links and buttons should be large enough to tap without error (minimum ~44px height)
- **Single-column layout** — multi-column desktop layouts should collapse to single-column on mobile. Flag if columns are still side-by-side and too narrow to read.
- **Images not scaling** — images should resize to fit the screen width, not overflow

---

## 6. Dark mode checks

Dark mode behaviour varies wildly. The checks below apply specifically to any screenshot labelled "(Dark Mode)" or "dm".

### Forced inversion clients — be most vigilant here
- **Outlook (Word engine) on Windows** — applies full automatic inversion with `!important` overrides. Most aggressive.
- **Gmail iOS** — full automatic colour inversion; no developer control
- **Gmail Android** — partial automatic inversion; background colours shift, images generally untouched (except small images under ~100px which may be inverted)
- **Outlook.com / New Outlook** — partial inversion with injected overrides; patchy and inconsistent

### Dark mode checks to run
- **Dark text on dark background** — the most common failure. Heading or body text becomes invisible because both it and the background were inverted separately to dark values. FAIL.
- **Light text on light background** — less common but occurs when only one element inverted. FAIL.
- **Logo/image transparency issues** — logos or icons with transparent backgrounds can disappear or develop halos when the background goes dark. Flag if a logo looks like it's missing or has an ugly white/coloured box around it.
- **Brand colour inversion** — CTA buttons, highlight colours, or branded sections with inverted colours that no longer match the brand. WARN if degraded, FAIL if the CTA becomes unreadable.
- **Patchy partial inversion** — some sections inverted, some not, creating an inconsistent patchwork of light and dark areas. Compare against the light-mode screenshot for the same client. WARN.
- **Pure white/black surfaces** — pure `#FFFFFF` and `#000000` trigger the most aggressive inversion. Look for sections that should be white-on-dark but appear black-on-black (or vice versa).

### Clients with no inversion (do not flag dark mode issues for these)
- **Apple Mail** — respects developer `@media (prefers-color-scheme: dark)` declarations. If the email has dark mode styles, they should render correctly here. Flag only if something looks unintentionally broken.
- **Outlook Mac** — same as Apple Mail
- **Yahoo Mail** — does not invert email content at all; renders as-is in dark mode
- **Gmail Web (desktop)** — does not invert email content

---

## Client-specific known issues

Use this section to know what to look for on specific clients before you even look at the screenshot.

### Outlook 2016 / 2019 / 2021 (Windows) — Word engine
The highest-risk clients. Expect and check for all of:
- Background images missing (CSS `background-image` not supported — VML required)
- `border-radius` ignored — all buttons and containers appear square
- Web fonts falling back to **Times New Roman** — whole layout may reflow
- Flexbox/grid layout collapsed — columns likely stacking
- `max-width` ignored — containers may stretch full width
- DPI scaling bug on high-res laptops — pixel values can be distorted, breaking spacing
- `padding` on `<div>` and `<p>` ignored — spacing may be wrong

### Outlook.com / New Outlook for Windows (Chromium)
Much better CSS support than Word engine, but:
- Partial dark mode inversion — check dark mode screenshots carefully
- Does not support MSO conditional comments (ghost tables/VML are ignored harmlessly)
- Generally renders well; flag anything unexpected

### Gmail Web (desktop)
- Strips external stylesheets entirely (linked `<link>` stylesheets are removed)
- **Media queries are supported** — responsive layout works normally
- **`background-image` in `<style>` blocks is supported** — CSS backgrounds render correctly
- 102KB clipping — if the email feels truncated, this may be why
- Strips: flexbox sub-properties, grid, transforms, animations, box-shadow, `position` other than `static`
- Dark mode: no inversion on desktop Gmail

### Gmail Android / iOS
- Android: partial colour inversion in dark mode
- iOS: full colour inversion in dark mode
- Small images (<100px) may be colour-inverted on Android dark mode
- Check these screenshots closely for dark mode issues

### Apple Mail (light and dark)
- Best rendering support — if something is broken here it's likely a genuine code bug
- Dark mode: checks `@media (prefers-color-scheme: dark)`. If email has no dark mode styles, Apple Mail may apply its own inversion. Flag if the dark mode screenshot looks unintentionally inverted.

### Samsung Mail
- Auto-fit content uses HTML `width` attribute to set viewport — wide images may force wide layout
- `margin` works on `<p>` and headings but NOT on `<div>` or `<table>` — gaps may be wrong
- `max-width` works on `<div>` and `<table>` but NOT on `<td>`
- If the Samsung account is configured with Exchange/Outlook, media queries are lost — check for layout collapse

### Yahoo Mail
- `height` is converted to `min-height` — images set to `height: auto` may not scale correctly
- CSS below HTML comments in `<style>` blocks is removed
- Does not invert email content in dark mode

---

## Severity guide

| Severity | Meaning |
|----------|---------|
| FAIL | Broken, unreadable, or missing content. A real user would have a bad experience. |
| WARN | Degraded but functional. Content is readable but looks wrong or off-brand. |

When in doubt between FAIL and WARN, ask: would a recipient notice this and think something is broken? If yes, FAIL.
