# Email QA Skill

A Claude skill that runs a full pre-send QA on a Marketo email. It fetches the email from Marketo, checks the HTML (UTMs, links, alt text, file size, spam keywords, Velocity tokens), reviews copy against your brand guidelines, sends the email to Email on Acid for rendering and optional spam tests, and returns a QA report with a PASS / WARN / BLOCK verdict.

## Setup

1. Connect the MCP servers the skill uses:
   - [Email on Acid MCP setup guide](https://info.knak.com/email-on-acid-mcp.html?utm_source=wfp-github&utm_medium=referral&utm_campaign=knak-labs-ong)
   - [Mailgun MCP setup guide](https://info.knak.com/mailgun-mcp.html?utm_source=wfp-github&utm_medium=referral&utm_campaign=knak-labs-ong)
   - A Marketo MCP server
2. Replace the example files in `references/` with your own:
   - `brand-guidelines.md` — your language rules and approved phrases
   - `utm-conventions.md` — your UTM rules and company domains
3. In `SKILL.md`, replace `yourcompany+default@precheck.emailonacid.com` with your Email on Acid precheck address and `<TEST_LEAD_ID>` with the Marketo ID of your test lead.

## Usage

Ask Claude to QA an email, for example: "Run QA on Marketo email 1234".
