# UTM & naming conventions (distilled for email QA)

> Source: example campaign tracking guide — replace with your own conventions.

## Email sends (primary rules for email QA)

Marketing emails use the **Email Send** channel:

- `utm_medium` = `email` (required on every web-property link)
- `utm_source` = one of: `eblast`, `event`, `newsletter`, `webinar`, `nurturing`, `sponsorship`
- `utm_campaign` = `[Product]-YYYY-MM-DD-[Description]`, lowercase, hyphen-separated
  (e.g. `email-2022-09-24-product-launch-promo`). Date may be `ong` for evergreen sends.
- `utm_content` = short description of the email content; may include `v1`/`v2` for split tests
  (e.g. `asia+conference+fall+promo`)

Marketo program name for email sends: `[Product]-ES-YYYY-MM-DD-[Description]`
(e.g. `EM-2022-09-24-Product Launch Promo`).

UTMs on email links exist for web analytics only — campaign membership is set via Marketo flow steps, not UTMs.

## Sales emails (if QA'ing sales cadence emails)

- `utm_medium` = `sales-email`; `utm_source` = `outreach`, `sales-insight`, `gmail`, `inmail`
- `utm_campaign` = `[BU]-ONG-[Description]` (e.g. `lp-ong-general-prospecting-cadence`)

## General naming anatomy

`[Type]-[Date]-[Platform]-[Description]` — date as `YYYY-MM-DD`, `YYYY-MM`, `YYYY`, or `ONG` (ongoing). In URLs, descriptions are hyphen-separated.

## Company web property domains (UTM rules apply to these only)

UTM parameters are only required on links to company-owned web properties. Only check UTMs on links whose hostname matches one of these domains (including any subdomain):

- `acme.com`
- `acme.io`
- `info.acme.com`

Every other link — social profiles, unsubscribe pages, view-in-browser, mailto:, third-party event platforms, etc. — is out of scope for UTM checking. Do not flag them.

## QA checks to run on every email

For each link whose hostname matches a company web property domain above:

1. It must carry `utm_medium=email` (exact value).
2. `utm_source` must be from the approved list above.
3. `utm_campaign` must match `[product]-YYYY-MM-DD-[description]` (or `-ong-`), all lowercase, hyphenated, and must be identical across all company-domain links in the email.
4. The email's Marketo program name follows `[Product]-ES-YYYY-MM-DD-[Description]`; the date in `utm_campaign` matches the program date.
5. `utm_content`, if present, must be a short hyphen/plus-separated description (optionally `v1`/`v2`).
