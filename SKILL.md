---
name: email-qa-eoa
description: >
  Run a comprehensive pre-send QA on a Marketo email. Use this skill whenever
  the user asks to QA an email, check an email before sending, run pre-send
  checks, test an email, validate email links or UTMs, or run an Email on Acid
  rendering test. Also triggers on "check this email", "is this email ready to
  send", "run QA on email ID", "review email before launch", or any request
  combining Marketo + email + quality check. The skill fetches the email HTML
  from Marketo, runs HTML analysis (UTMs, links, alt text, file size, spam
  keywords, Velocity tokens), sends it to Email on Acid for rendering tests,
  fans out parallel subagents to visually review each screenshot, runs optional
  spam filter testing, and outputs a human-readable QA report.
---

# Email QA — Email on Acid

You are running a comprehensive pre-send email QA for a marketing ops team.

---

## How questions work in this skill

**Do not use AskUserQuestion at any point.** All questions are asked as plain text at the end of a chat message. The user types their reply and you continue. This keeps questions and results in the same readable message, and avoids modal overlays that hide the report.

---

## Reference files

Read all three files in parallel **at the same time as you spawn the Step 2 subagent** — they are not needed until Step 3, so there is no reason to read them before spawning. Include all three Read calls and the Agent call in a single parallel message:

- `references/utm-conventions.md` — Your company's UTM naming rules (required values, format patterns, exemptions)
- `references/brand-guidelines.md` — Your company's language rules (approved phrases, "never say" terms, positioning rules)
- `references/rendering_checks.md` — Visual checklist for screenshot review: what to look for per client, dark mode rules, known client-specific bugs
- Any other `.md` files in `references/` — additional context docs

---

## Severity framework

| Severity | Meaning | Blocks send? |
|----------|---------|-------------|
| 🔴 CRITICAL | Major deliverability, legal, or broken-CTA issue. Must fix now. | Yes |
| 🟠 HIGH | Clearly broken or wrong — should fix before sending. | Recommended |
| 🟡 MEDIUM | Approaching a limit or minor deviation — fix in next version. | No |
| 🔵 LOW | Nice to have. | No |

**Overall verdict:**
- ✅ **PASS** — 0 Critical, 0 High
- ⚠️ **WARN** — 0 Critical, 1+ High
- ❌ **BLOCK** — 1+ Critical

---

## Before you begin

### Document digestion (runs before Step 1 whenever the user shares a file)

If the user shares any document — PDF, DOCX, XLSX, MD, TXT — digest it before proceeding to Step 1.

1. Read the file (use `python3 -c "import docx; ..."` for DOCX, `pdftotext` for PDF).
2. Distill it into a concise `.md` file — strip boilerplate, keep rules and facts.
3. Save it to `references/<descriptive-name>.md`.
4. Tell the user: "I've ingested [filename] and saved the key rules to `references/<name>.md`."

If a reference file with the same name already exists, offer to overwrite it or keep both.

- Messaging/brand docs → merge into `brand-guidelines.md` or save as new file
- UTM/tracking docs → merge into `utm-conventions.md` or save separately
- Campaign briefs → save as `brief-<description>.md`

### Config check (first run only)

Check whether `~/.email-qa-config.json` exists. If not, create it silently:

```json
{
  "utm_conventions_loaded_from": "references/utm-conventions.md",
  "setup_complete": true
}
```

### Progress communication

Post a one-line status update before each major step. Never go silent during long operations.

- Before Step 2: "Fetching email [ID] from Marketo…"
- Before Step 3: "Running HTML checks…"
- Before Step 6: "Submitting to Email on Acid…"
- During Step 7 polling: after every poll — "Waiting for EOA rendering results — X / Y clients complete."
- When launching screenshot subagents: "All clients complete — reviewing screenshots in parallel now…"

---

## Step 1 — Get the email ID

If the user already provided a Marketo email ID in their message, extract it and skip to Step 2.

If no ID was provided, reply: **"What Marketo email ID should I QA? If you have a campaign brief, you can upload it now too."** Wait for their reply before continuing.

---

## Step 2 — Fetch email content and run automated checks (subagent)

**When to spawn:** In the same parallel message as your reference file reads (see above). Do not wait for reference files before spawning — they aren't needed until Step 3.

**What to pass to the subagent:** Include the skill base directory path in the subagent's instructions. Your session context contains a line like `Base directory for this skill: /var/folders/...` — pass that exact path as `SKILL_DIR` so the subagent doesn't have to search for it. Searching for the path is the single biggest cause of slow runs.

The subagent must not ask any questions or wait for user input — just fetch, run, and return.

**The subagent makes all 4 Marketo API calls in a single parallel message (multiple tool_use blocks in one response):**
- `getEmailFullContentUsingGET` with `id` and `type: "HTML"` → extract HTML string, write to `/tmp/email_qa_<id>.html`
- `getEmailFullContentUsingGET` with `id` and `type: "Text"` → extract plain text, write to `/tmp/email_qa_<id>_plaintext.txt`
- `getEmailByIdUsingGET` with `id` → extract `{subject, fromEmail, fromName, replyTo, preheader}`, write to `/tmp/email_qa_<id>_meta.json`
- `getEmailVariablesUsingGET` with `id` → extract variable list, write to `/tmp/email_qa_<id>_variables.json`

**After all 4 API calls return, the subagent runs the QA script using the SKILL_DIR passed to it:**

```bash
python3 $SKILL_DIR/scripts/html_qa.py \
  --html-file /tmp/email_qa_<id>.html \
  --subject "<subject from metadata>" \
  --preview-text "<preheader from metadata>" \
  --plain-text "<text version content>" \
  --output /tmp/email_qa_results_<id>.json
```

The script checks:

| Check | Threshold | Severity |
|-------|-----------|----------|
| Subject line non-empty | BLOCK if empty | 🔴 CRITICAL |
| Subject line length | PASS ≤50 / MEDIUM 51–70 / HIGH >70 chars | 🟡/🟠 |
| Preview text exists | BLOCK if missing or <15 chars | 🔴 CRITICAL |
| Preview text length | Flag if >80 chars | 🟡 MEDIUM |
| Plain text version exists | Flag if empty | 🟡 MEDIUM |
| Plain text quality | Flag if <50% of HTML word count | 🟡 MEDIUM |
| Plain text has URLs | Flag if links appear truncated | 🟡 MEDIUM |
| HTML file size | PASS <80KB / MEDIUM 80–102KB / HIGH >102KB | 🟡/🟠 |
| Alt text on images | HIGH per `<img>` missing alt (tracking pixels exempt) | 🟠 HIGH |
| Button links | CRITICAL per button with empty/missing href | 🔴 CRITICAL |
| Text links validity | HIGH per `<a>` with "#" or "javascript:" href | 🟠 HIGH |
| UTM params structurally present | HIGH per tracked link missing utm_source/medium/campaign | 🟠 HIGH |
| UTM params not empty/unfilled | HIGH per link with `{{token}}` in UTM value | 🟠 HIGH |
| Image file types | MEDIUM per unsupported format (.tiff/.bmp) | 🟡 MEDIUM |
| Image file sizes | MEDIUM >200KB / HIGH >500KB / MEDIUM GIF >1MB | 🟡/🟠 |
| Unsubscribe link present | CRITICAL if no unsubscribe/preferences link found | 🔴 CRITICAL |
| Physical address in footer | CRITICAL if no street address found in footer | 🔴 CRITICAL |
| JavaScript or iframes | CRITICAL if any `<script>` or `<iframe>` found | 🔴 CRITICAL |
| Velocity tokens unfilled | HIGH per `{{token}}` left in HTML | 🟠 HIGH |
| Text-to-image ratio | MEDIUM if >3 images per 50 words | 🟡 MEDIUM |

**The subagent returns to the main agent:**
- The script JSON output (from `/tmp/email_qa_results_<id>.json`)
- The metadata (subject, preheader, from, etc.)
- The variable list (for token fallback checks)
- The file paths for HTML and plaintext (for the main agent's manual checks)

---

## Step 3 — Manual HTML checks (main agent)

With the data returned by the subagent, do all manual checks now. **Read the HTML file once** using the Read tool, then perform all of 3a–3e from that single read — do not call bash or Read again per sub-check.

> **Note on link checking:** The bash sandbox proxy allowlist covers PyPI/GitHub, your company's web properties (`acme.com`, `acme.io`, `info.acme.com`), and major social platforms (LinkedIn, X/Twitter, Facebook, YouTube, Instagram, TikTok). The script has already extracted `http_links` from the HTML for use in Step 4b.

### 3a — UTM semantic validation

Using the rules in `references/utm-conventions.md`, check every tracked link:

- `utm_medium` must be exactly `email` (or `sales-email` for sales emails)
- `utm_source` must be from the approved list: `eblast`, `event`, `newsletter`, `webinar`, `nurturing`, `sponsorship`
- `utm_campaign` must match `[product]-YYYY-MM-DD-[description]` (or `-ong-`), all lowercase and hyphen-separated, and must be **identical across all links**
- `utm_content`, if present, must be a short hyphen/plus-separated description
- **Only check UTMs on company-owned domains**: `acme.com`, `acme.io`, `info.acme.com` (including subdomains). Social profiles, unsubscribe, view-in-browser, third-party platforms — all exempt. See `references/utm-conventions.md` for full list.

Flag any deviation as 🟠 HIGH with the exact URL and specific rule broken.

### 3b — Content & brand checks

#### Grammar & proofreading
- Spelling errors, typos, grammatical mistakes → 🟠 HIGH per instance
- Repeated paragraphs or duplicate sentences → 🟠 HIGH
- Broken sentence structure → 🟡 MEDIUM

#### Subject line + preheader complement
- Preheader should extend the subject, not repeat it word-for-word → 🟡 MEDIUM if repetitive
- Neither should be blank or default to "View in browser"
- Subject should immediately convey the value — flag if ambiguous → 🟡 MEDIUM
- Preheader must not contain stray HTML entities (`&amp;`, `%20`, raw `{{` tokens) → 🟡 MEDIUM

#### CTA above the fold
- At least one primary CTA visible on desktop without scrolling → 🟡 MEDIUM if CTA only appears at the bottom
- CTA button text should use action verbs and sentence case
- One primary CTA — multiple equally prominent CTAs dilute focus → 🟡 MEDIUM

#### Alt text quality
- Alt text should convey the image's purpose — "Woman using Acme email builder" is good; "image", "banner" is not → 🟡 MEDIUM per vague alt
- Decorative spacer images should have `alt=""` — flag if they have descriptive text → 🟡 MEDIUM

#### Brand language
Using `references/brand-guidelines.md`:
- Any "never say" terms → 🔴 CRITICAL. Quote the violating sentence and name the rule.
- Scope misuse (e.g. "production system" in everyday copy) → 🟡 MEDIUM
- Leading with asset types (emails, landing pages) in hero copy → 🟡 MEDIUM

If a brief was uploaded, compare CTA text, offer details, key claims → flag discrepancies as 🟡 MEDIUM (may be intentional).

### 3c — Accessibility checks

#### WCAG colour contrast

Calculate the actual WCAG contrast ratio for text on coloured backgrounds — do not just flag "verify contrast."

1. Extract hex `color` and `background-color` from inline CSS
2. Normalize each RGB channel to 0–1, then linearize:
   - If c ≤ 0.03928 → `c / 12.92`
   - Else → `((c + 0.055) / 1.055) ^ 2.4`
3. Relative luminance: `L = 0.2126·R + 0.7152·G + 0.0722·B`
4. Contrast ratio: `(L_lighter + 0.05) / (L_darker + 0.05)`

Thresholds (WCAG AA):
- Normal body text (<18pt or <14pt bold): must be ≥ 4.5:1 → below = 🟠 HIGH
- Large text (≥18pt or ≥14pt bold): must be ≥ 3:1 → below = 🟠 HIGH
- Borderline (within 10% of threshold): → 🟡 MEDIUM, quote the exact ratio

Focus on: CTA button text vs background, hero headline vs background, body text vs card background.

#### Descriptive link text
Flag any `<a>` where the visible text is vague: "click here", "here", "read more", "learn more" (without a qualifying noun) → 🟡 MEDIUM per instance.

#### Heading hierarchy
Headings must not skip levels (h1 → h3 with no h2). At most one `<h1>`. → 🟡 MEDIUM if violated. Note: `<p>` tags styled as headings don't count — only flag actual heading tag misuse.

#### Minimum font size
Any inline `font-size` below 14px in body text → 🟡 MEDIUM. Legal footers (10–12px) are acceptable.

### 3d — Marketo token fallback check

Using the variable list returned by the subagent, check each token: does it have a default/fallback value set? Flag any token with no fallback as 🟡 MEDIUM — "Token `{{my.token-name}}` has no fallback value; if empty for a lead the field will render blank."

If the API didn't return fallback data, note it as a manual check.

---

## Step 4 — Post HTML QA results and ask about link testing

Write the full HTML QA report (use the format from Step 9, HTML checks section only — no rendering section yet).

At the end of the same message, ask:

> **"Would you like me to test the links in this email? Reply with: all links, body links only, or skip."**

Wait for the user's reply, then proceed to Step 4b or Step 5.

### 4b — Run link tests (if requested)

Extract the link list from `http_links` in the script's JSON output.

Apply the user's scope:
- **All links**: every HTTP/HTTPS link
- **Body links only**: exclude — unsubscribe/optout/preferences, viewaswebpage/webversion, social profiles (x.com, twitter.com, linkedin.com, facebook.com, youtube.com, instagram.com, tiktok.com), and the first link if it wraps a logo image

**Spawn one subagent per link in a single message so they all run in parallel.** Each subagent receives the URL, its link text, and these instructions:

```
Check whether this URL is reachable AND whether the destination makes sense for the link text.

LINK TEXT: "<link text from HTML>"
URL: "<url>"

1. Reachability — try in order, stop at the first that works:

   curl (fastest):
   code=$(curl -s -o /dev/null -w "%{http_code}" -L --max-time 8 "<url>")
   - 200/301/302/303/307/308 → reachable
   - 4xx/5xx → broken
   - 000 → proxy blocked, move to web_fetch

   web_fetch (fallback if curl returns 000):
   Call mcp__workspace__web_fetch on the URL.

2. Semantic validation — if reachable, check whether the destination fits the link text:
   - "Get started" / "Start free trial" → must reach signup or pricing, not homepage
   - "Book a demo" → must reach a demo booking page
   - "Learn more about [feature]" → must reach a relevant help/product page
   - Logo link → homepage or dashboard is fine
   - Social icons → must reach the correct brand social profile
   - Vague link text ("here", "click here", "read more") → flag the text itself

Report back:
- url, link_text, method ("curl"|"web_fetch"), http_code, final_url
- reachable: true|false
- semantic_match: true|false|null
- severity: "CRITICAL" (primary CTA broken) | "HIGH" (secondary broken or semantic mismatch) | "MEDIUM" (right area, wrong page) | "ok"
- note: plain English summary or "ok"
```

If there is only one link, run the check directly — no subagent needed.

---

## Step 5 — Post link results and ask about Email on Acid

Write the link test results (use the links section format from the Report Format section below).

At the end of the same message, ask:

> **"Would you like to run Email on Acid tests? This will consume EOA credits. Reply with what you want:
>
> - **Rendering only** — previews across email clients (~1 minute). Client list: `defaults` or list specific clients (e.g. "Gmail, Outlook 2021, iPhone 15").
> - **Rendering + spam filter** — also checks against major spam filters (spam results take up to 10 minutes).
> - **No** — skip EOA entirely."**

If no: deliver the final HTML + link report and stop.

Wait for the user's reply before continuing to Step 6.

---

## Step 6 — Send from Marketo to Email on Acid

Rather than uploading HTML directly to EOA, send the email through Marketo's real pipeline. This ensures rendering tests reflect actual MIME encoding, click-tracking rewrites, and real sending headers — the same email the recipient would receive.

### 6a — Rendering test (always)

Call `sendSampleEmailUsingPOST` with:
- `id`: the Marketo email ID
- `emailAddress`: `yourcompany+default@precheck.emailonacid.com` (replace with your EOA precheck address)
- `leadId`: `<TEST_LEAD_ID>` (replace with the Marketo ID of your test lead)

Post immediately after the call returns:
> "Email sent to EOA precheck inbox — waiting for EOA to create the rendering test…"

Wait 15 seconds, then poll `getEmailTests` every 10 seconds for up to 90 seconds. Each poll, filter the results by subject line to find the auto-created test. After each attempt post: "Polling for EOA test — attempt X / 9…"

If the test is found:
> "Rendering test created — ID: `<test_id>`
> - 🖥 Rendering results ready in ~1 minute.
>
> **Would you like me to retrieve the rendering screenshots? I'll poll until they're ready. Reply yes or no.**"

If not found after 90 seconds:
> "EOA hasn't picked up the email yet — this occasionally happens if the precheck inbox is slow. Check https://app.emailonacid.com directly — the test may appear shortly. You can also reply with the test ID manually and I'll use it."

### 6b — Spam seed test (only if spam was requested)

Run this in parallel with 6a (include both tool calls in the same message as the `sendSampleEmailUsingPOST` call above, or immediately after).

Call `createSpamTest` with:
- `subject`: from email metadata
- `html`: full HTML from `/tmp/email_qa_<id>.html`
- `test_method`: `"seed"`

This returns a `spam_test_id` and an `address_list` of 12 seed addresses. Immediately send the email to all 12 addresses in a **single parallel message** (one `sendSampleEmailUsingPOST` call per address, all in one response):

```
sendSampleEmailUsingPOST(id: <email_id>, emailAddress: <seed_address>, leadId: <TEST_LEAD_ID>)
```

After all 12 sends complete, post:
> "Spam seed test `<spam_test_id>` — email sent from Marketo to all 12 seed addresses.
> Results take 5–20 minutes. Some ISP inboxes (Yahoo, AOL) may not return a result if those providers filter the email.
>
> Say 'check spam results' when you're ready and I'll pull them."

Store `spam_test_id` — you will need it in Step 8.

---

## Step 7 — Poll for rendering results and review screenshots

If the user says yes, poll `getEmailTest` every 15 seconds. After every poll, post:

> "Waiting for EOA rendering results — X / Y clients complete."

If all clients are complete on the first poll: "EOA results are in — all X clients complete. Reviewing screenshots now…"

If polling runs more than 90 seconds with no change: "EOA is still processing — this occasionally takes a few minutes. Still watching…"

Once all done, call `getEmailTestResults` to get screenshot URLs.

**Important:** Presigned screenshot URLs expire after 24 hours — process them promptly.

Spread completed (non-Bounced) results across **up to 10 subagents** — one client per subagent if ≤10 clients, otherwise distribute evenly (e.g. 20 clients → 10 subagents of 2 each). **Spawn all subagents in a single message so they all run in parallel.** Each subagent receives its assigned clients, the full text of `references/rendering_checks.md`, and these instructions:

```
You are reviewing email rendering screenshots for QA issues.

How to view each screenshot:
1. curl -s -o /tmp/eoa_<client_id>.png "<screenshot_url>"
2. test -s /tmp/eoa_<client_id>.png && echo ok || echo empty
3. If ok: use the Read tool on /tmp/eoa_<client_id>.png to visually inspect it
4. If empty: load Chrome tools via ToolSearch "select:mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer", navigate to screenshot_url, use computer() to capture

For each client in your batch:
1. Download and view the screenshot
2. Check it against EVERY section of the rendering_checks.md provided:
   - Layout (broken columns, gaps, overflow, container width)
   - Text & typography (clipped copy, font fallbacks to Times New Roman, small mobile text)
   - Images (broken icons, missing backgrounds, blurry retina, blocked images)
   - Buttons/CTAs (invisible, collapsed padding, low contrast, small tap targets)
   - Mobile (viewport overflow, tiny fonts, columns not stacking)
   - Dark mode: dark text on dark background, logo halos, brand colour inversion, patchy inversion
   - Client-specific known issues: check the relevant section in rendering_checks.md before inspecting
3. Return a JSON array of all issues (empty array if none):
   [{"client_id":"","client_name":"","os":"","category":"layout|text|images|buttons|mobile|dark_mode","issue":"plain English","severity":"MEDIUM|HIGH","screenshot_url":"<url>"}]

Severity:
- HIGH: broken/unreadable — real user would have a bad experience
- MEDIUM: degraded but functional — looks wrong or off-brand

Report every issue per client, not just the first. Include screenshot_url in each issue.
```

Collect all subagent results into a single `rendering_issues` array.

Display the rendering section of the report (format below).

At the end of the rendering results message, ask:

> **"Would you like me to check the spam filter results now? Some filters return within minutes, others take up to 10 minutes. I'll do a single check — if they're not ready yet I'll let you know. Reply yes or no."**

---

## Step 8 — Spam filter results

If spam was not requested, skip this step entirely.

If the user says yes (or says "check spam results"), call `getSpamTestResults` with the `spam_test_id` stored in Step 6b — **once only**, do not loop.

If results are available, display the spam filter section of the report. Note that:
- `spam: -1` = not spam ✅
- `spam: 1` = flagged as spam 🔴
- `spam: 0` = inconclusive ⚪
- `spam: null` = no result returned — most commonly Yahoo and AOL, which are real ISP mailboxes. If these ISPs filtered or rate-limited the Marketo send, EOA can't monitor the inbox and the result stays null. This is a deliverability signal, not a tool failure.

If results are still pending (all null):

> "Spam results aren't back yet — filters can take up to 20 minutes. Just reply 'check spam results' when you're ready and I'll pull them."

Do not poll again automatically. Wait for the user to prompt you.

---

## Report format

Write the report in plain language — no jargon, describe the problem and what needs to change.

### Overall verdict

> ✅ **PASS** — 0 Critical, 0 High issues. Email is ready to send.
> ⚠️ **WARN** — No blocking issues, but X High items should be fixed before sending.
> ❌ **BLOCK** — X Critical issue(s) must be resolved before this email goes out.

### HTML checks

Group by severity. Show passing checks as a single summary line. Lead with Critical → High → Medium → Low.

```
HTML CHECKS  ✅ 12 passed  🟡 2 medium  🟠 1 high

🟠 HIGH
  • Subject line is 74 characters — will be truncated in Gmail and Outlook.
    Fix: shorten to under 50 characters.

🟡 MEDIUM
  • HTML file size is 89 KB — approaching Gmail's 102 KB clipping limit.
```

For each issue: describe the problem, quote the specific value, and say what the correct value should be.

### Links

```
LINKS  X / X checked  (via curl / web_fetch)

✅ All links resolved and destinations match link text.

— or —

🔴 CRITICAL:
  • "Get started" → https://acme.com/blog/post → Reaches blog post, not signup

🟠 HIGH:
  • https://acme.com/broken → 404 Not Found

🟡 MEDIUM:
  • "Learn more" → https://acme.com/ → Reaches homepage, not a specific feature page

⚠️ Blocked (proxy — verify manually):
  • https://example.com → curl blocked, web_fetch also failed
```

### Rendering

```
RENDERING  X / X clients tested

🟠 Clients with HIGH issues (X):
  • Gmail App Pixel 6 (Android 12, Dark Mode) — CTA button inverted, text unreadable
  • Outlook 2019 (Windows 10) — hero image not loading, showing alt text only

🟡 Clients with MEDIUM issues (X):
  • iPhone 16 Pro (iOS 18) — footer text slightly truncated on narrow viewport

✅ All other clients rendered correctly.
```

Name every client with an issue. Describe what's broken as if the reader can't see the screenshot.

### Spam (if requested)

```
SPAM FILTER TESTING
  📬 Test in progress — results take ~15–20 minutes.
  Spam test ID: <spam_test_id>
  Reply "check spam test results" when you're ready and I'll pull them.
```

If results are already available:

```
SPAM FILTER TESTING
  ✅ Passed all filters  /  🟠 Flagged by X filter(s): [names and details]
```

### Footer

```
View full results in EOA: https://app.emailonacid.com/app/acidtest/<test_id>/list
```

At the end of the message, ask:

> **"Would you like me to save the screenshots for clients with issues so you can review them? Reply yes or no."**

If yes:
1. Create `eoa-screenshots-<email_id>/` in the workspace
2. For each client with issues: `curl -s -o "eoa-screenshots-<email_id>/<client_name>.png" "<screenshot_url>"`
3. Call `present_files` with every downloaded PNG

Do not build an HTML file or widget — present raw PNGs via `present_files`.

---

## Notes

- Bounced clients in EOA = infrastructure issue, not email problem — exclude from counts but mention them
- `spam: 1` = flagged / `spam: -1` = not spam / `spam: 0` = inconclusive
- Brief mismatches are MEDIUM only — may be intentional
- Never click the unsubscribe link in a proof email — it will unsubscribe the test inbox
- The future email-fixing skill will read this report directly — write issues clearly enough that the fix is obvious without re-examining the email
