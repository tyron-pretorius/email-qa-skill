#!/usr/bin/env python3
"""
Email HTML QA script for email-qa-eoa skill.
Runs all HTML-level checks and outputs structured JSON results.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs

UNSUPPORTED_IMAGE_TYPES = [".tiff", ".tif", ".bmp", ".psd", ".raw"]

# URL patterns that identify tracking pixels — skip alt text and size checks for these.
TRACKING_PIXEL_URL_PATTERNS = [
    "k-trk.com", "ktrack", "trk.", "/track/", "/open/", "/beacon/",
    "mailchimp.com/track", "mktoopen", "open.aspx", "open.php",
    "click.exacttarget", "t.sidekickopen", "emltrk.com",
]

def is_tracking_pixel(img: dict) -> bool:
    """Return True if this image is a tracking pixel and should be excluded from content checks."""
    src = img.get("src", "").lower()
    # URL pattern match
    if any(pat in src for pat in TRACKING_PIXEL_URL_PATTERNS):
        return True
    return False

# Marketo Velocity token patterns
VELOCITY_UNFILLED = re.compile(r"\{\{[^}]+\}\}")
VELOCITY_DIRECTIVE = re.compile(r"#(define|evaluate|set|if|else|end|foreach)\b")


class EmailHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []          # list of {"src": ..., "alt": ...}
        self.links = []           # list of href strings
        self.buttons = []         # list of {"href": ..., "text": ...}
        self.text_parts = []      # visible text content
        self.has_unsubscribe = False
        self._in_button = False
        self._current_button_href = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == "img":
            self.images.append({
                "src": attrs_dict.get("src", ""),
                "alt": attrs_dict.get("alt", None),
            })

        if tag == "a":
            href = attrs_dict.get("href", "")
            self.links.append(href)
            if any(k in href.lower() for k in ["unsubscribe", "optout", "opt-out", "email-preferences", "manage-preferences"]):
                self.has_unsubscribe = True
            # Check for table-based buttons (common in email HTML)
            role = attrs_dict.get("role", "")
            if role == "button" or "btn" in attrs_dict.get("class", "").lower():
                self.buttons.append({"href": href})

        if tag in ("button",):
            href = attrs_dict.get("href", attrs_dict.get("onclick", ""))
            self._in_button = True
            self._current_button_href = href

    def handle_endtag(self, tag):
        if tag == "button":
            self.buttons.append({"href": self._current_button_href or ""})
            self._in_button = False
            self._current_button_href = None

    def handle_data(self, data):
        stripped = data.strip()
        if stripped:
            self.text_parts.append(stripped)


def run_check(check_name, status, value, message, fix_target, fix_action=""):
    return {
        "check": check_name,
        "status": status,
        "value": str(value),
        "message": message,
        "fix_target": fix_target,
        "fix_action": fix_action,
    }


def check_subject(subject):
    results = []
    if not subject or not subject.strip():
        results.append(run_check(
            "subject_line_empty", "FAIL", subject,
            "Subject line is empty.",
            "marketo", "Set a subject line in Marketo."
        ))
        return results

    length = len(subject)
    if length <= 50:
        status, msg = "PASS", f"Subject line is {length} characters."
    elif length <= 70:
        status, msg = "WARN", f"Subject line is {length} characters (>50 — may be truncated on mobile)."
    else:
        status, msg = "FAIL", f"Subject line is {length} characters (>70 — will be truncated in Gmail desktop and most mobile clients)."

    results.append(run_check(
        "subject_line_length", status, length, msg,
        "marketo", "Shorten the subject line to under 50 characters."
    ))

    return results


def check_preview_text(preview_text):
    results = []
    if not preview_text or len(preview_text.strip()) < 15:
        results.append(run_check(
            "preview_text_length", "FAIL",
            len(preview_text.strip()) if preview_text else 0,
            "Preview text is missing or fewer than 15 characters.",
            "marketo", "Add preview text of 15–80 characters in Marketo."
        ))
    elif len(preview_text) > 80:
        results.append(run_check(
            "preview_text_length", "WARN", len(preview_text),
            f"Preview text is {len(preview_text)} characters (>80 — may be truncated).",
            "marketo", "Shorten preview text to 80 characters or fewer."
        ))
    else:
        results.append(run_check(
            "preview_text_length", "PASS", len(preview_text),
            f"Preview text is {len(preview_text)} characters.", "none"
        ))
    return results


def check_html_size(html_content):
    size_bytes = len(html_content.encode("utf-8"))
    size_kb = size_bytes / 1024
    if size_kb < 80:
        status, msg = "PASS", f"HTML size is {size_kb:.1f} KB."
    elif size_kb <= 102:
        status, msg = "WARN", f"HTML size is {size_kb:.1f} KB (approaching Gmail's 102 KB clipping threshold — leave room for ESP tracking injection)."
    else:
        status, msg = "FAIL", f"HTML size is {size_kb:.1f} KB — Gmail will clip this email at 102 KB."
    return [run_check(
        "html_file_size", status, f"{size_kb:.1f} KB", msg,
        "knak", "Reduce HTML size by removing unused styles, shortening URLs, or splitting content."
    )]


def check_alt_text(images):
    results = []
    content_images = [img for img in images if not is_tracking_pixel(img)]
    missing = [img for img in content_images if img["alt"] is None]
    if missing:
        for img in missing:
            results.append(run_check(
                "alt_text_missing", "FAIL", img["src"][:80],
                f"Image is missing alt text: {img['src'][:80]}",
                "knak", "Add descriptive alt text to this image in the Knak template."
            ))
    else:
        results.append(run_check(
            "alt_text", "PASS", f"{len(content_images)} images",
            "All content images have alt text (tracking pixels excluded).", "none"
        ))
    return results


def check_links(links):
    results = []
    bad = [h for h in links if h in ("#", "javascript:void(0)", "javascript:", "") or h.startswith("javascript:")]
    if bad:
        for href in bad:
            results.append(run_check(
                "invalid_link", "FAIL", href or "(empty)",
                f"Link has an invalid or empty href: '{href}'",
                "knak", "Set a valid destination URL for this link."
            ))
    else:
        results.append(run_check(
            "text_links", "PASS", f"{len(links)} links",
            "All links have valid href destinations.", "none"
        ))
    return results


def check_buttons(buttons):
    results = []
    bad = [b for b in buttons if not b.get("href") or b["href"] in ("#", "")]
    if bad:
        for b in bad:
            results.append(run_check(
                "button_link_missing", "FAIL", b.get("href", "(empty)"),
                "A button element has no link destination.",
                "knak", "Set a valid destination URL for this button in the Knak template."
            ))
    elif buttons:
        results.append(run_check(
            "button_links", "PASS", f"{len(buttons)} buttons",
            "All buttons have link destinations.", "none"
        ))
    return results


def check_unsubscribe(has_unsubscribe, links):
    # Also scan link text for unsubscribe patterns in raw HTML (handled by parser)
    if has_unsubscribe:
        return [run_check(
            "unsubscribe_link", "PASS", "found",
            "Unsubscribe or email preferences link detected.", "none"
        )]
    return [run_check(
        "unsubscribe_link", "FAIL", "not found",
        "No unsubscribe or email preferences link found — required for CAN-SPAM compliance.",
        "marketo", "Add an unsubscribe link or Marketo {{system.unsubscribeLink}} token."
    )]


def check_velocity_tokens(html_content):
    results = []
    unfilled = VELOCITY_UNFILLED.findall(html_content)
    directives = VELOCITY_DIRECTIVE.findall(html_content)

    if unfilled:
        for token in set(unfilled):
            results.append(run_check(
                "velocity_token_unfilled", "FAIL", token,
                f"Unfilled Velocity token found: {token}",
                "marketo", f"Fill or remove the token {token} in Marketo."
            ))
    else:
        results.append(run_check(
            "velocity_tokens", "PASS", "none unfilled",
            "No unfilled Velocity tokens detected.", "none"
        ))

    total = len(VELOCITY_UNFILLED.findall(html_content)) + len(directives)
    if total > 200:
        results.append(run_check(
            "velocity_token_count", "WARN", total,
            f"High Velocity token count ({total}) — approaching Marketo processing limits.",
            "marketo", "Reduce token count or simplify dynamic content logic."
        ))

    return results


def check_image_types(images):
    results = []
    for img in images:
        src = img["src"].lower().split("?")[0]
        for ext in UNSUPPORTED_IMAGE_TYPES:
            if src.endswith(ext):
                results.append(run_check(
                    "image_file_type", "WARN", img["src"][:80],
                    f"Image uses an unsupported file type ({ext}): {img['src'][:80]}",
                    "knak", f"Convert this image to JPG, PNG, or GIF."
                ))
    if not any(r["check"] == "image_file_type" for r in results):
        results.append(run_check(
            "image_file_types", "PASS", f"{len(images)} images",
            "All images use supported file types.", "none"
        ))
    return results


def check_text_image_ratio(images, text_parts):
    images = [img for img in images if not is_tracking_pixel(img)]
    image_count = len(images)
    word_count = sum(len(t.split()) for t in text_parts)
    ratio_ok = (image_count == 0) or (word_count / image_count >= 50 / 3)
    if not ratio_ok and image_count > 0:
        return [run_check(
            "text_image_ratio", "WARN",
            f"{image_count} images / {word_count} words",
            f"Email appears image-heavy ({image_count} images, ~{word_count} words of text). Heavy image ratios can trigger spam filters.",
            "knak", "Add more text content or reduce the number of images."
        )]
    return [run_check(
        "text_image_ratio", "PASS",
        f"{image_count} images / {word_count} words",
        "Text-to-image ratio looks healthy.", "none"
    )]


def check_utm_params(links, config):
    utm_config = config.get("utm_conventions", {})
    required_params = ["utm_source", "utm_medium", "utm_campaign"]
    results = []
    tracked = [h for h in links if h.startswith("http://") or h.startswith("https://")]
    unique_tracked = list(set(tracked))

    issues = 0
    for url in unique_tracked:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        for param in required_params:
            if param not in params:
                results.append(run_check(
                    "utm_param_missing", "FAIL", url[:80],
                    f"Link is missing {param}: {url[:80]}",
                    "marketo", f"Add {param} to this link's UTM parameters."
                ))
                issues += 1
            else:
                val = params[param][0]
                if not val or val.startswith("{{") or "%7B%7B" in val:
                    results.append(run_check(
                        "utm_param_unfilled", "FAIL", url[:80],
                        f"Link has unfilled {param} token: {url[:80]}",
                        "marketo", f"Fill in the {param} value for this link."
                    ))
                    issues += 1

    if issues == 0 and unique_tracked:
        results.append(run_check(
            "utm_parameters", "PASS", f"{len(unique_tracked)} tracked links",
            "All tracked links have UTM parameters populated.", "none"
        ))
    elif not unique_tracked:
        results.append(run_check(
            "utm_parameters", "WARN", "0 tracked links",
            "No tracked HTTP/HTTPS links found in the email.", "none"
        ))

    return results


def extract_http_links(links):
    """Return unique HTTP/HTTPS links, excluding mailto/tel."""
    return sorted(set(
        h for h in links
        if (h.startswith("http://") or h.startswith("https://"))
        and not h.startswith("mailto:") and not h.startswith("tel:")
    ))


def check_image_sizes(images):
    results = []
    images = [img for img in images if not is_tracking_pixel(img)]

    # Probe connectivity before attempting HEAD requests
    try:
        probe = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "--max-time", "5", "-I", "https://www.google.com"],
            capture_output=True, text=True, timeout=8
        )
        code = probe.stdout.strip()
        if code == "000" or probe.returncode not in (0, 6):
            return [run_check(
                "image_file_sizes", "WARN", "skipped",
                "Image size check skipped — outbound network access is restricted in this environment.",
                "none"
            )]
    except Exception:
        return [run_check(
            "image_file_sizes", "WARN", "skipped",
            "Image size check skipped — network connectivity probe failed.", "none"
        )]

    for img in images:
        src = img["src"]
        if not src.startswith("http"):
            continue
        try:
            result = subprocess.run(
                ["curl", "-s", "-I", "--max-time", "10", src],
                capture_output=True, text=True, timeout=15
            )
            for line in result.stdout.splitlines():
                if line.lower().startswith("content-length:"):
                    size_bytes = int(line.split(":")[1].strip())
                    size_kb = size_bytes / 1024
                    is_gif = src.lower().split("?")[0].endswith(".gif")

                    if is_gif and size_kb > 1024:
                        results.append(run_check(
                            "image_file_size", "WARN", f"{size_kb:.0f} KB",
                            f"Animated GIF exceeds 1 MB ({size_kb:.0f} KB): {src[:80]}",
                            "knak", "Reduce GIF file size or number of frames."
                        ))
                    elif size_kb > 500:
                        results.append(run_check(
                            "image_file_size", "FAIL", f"{size_kb:.0f} KB",
                            f"Image exceeds 500 KB ({size_kb:.0f} KB): {src[:80]}",
                            "knak", "Compress or resize this image."
                        ))
                    elif size_kb > 200:
                        results.append(run_check(
                            "image_file_size", "WARN", f"{size_kb:.0f} KB",
                            f"Image exceeds 200 KB ({size_kb:.0f} KB): {src[:80]}",
                            "knak", "Consider compressing this image for faster load times."
                        ))
                    break
        except Exception:
            pass

    if not any(r["check"] == "image_file_size" for r in results):
        results.append(run_check(
            "image_file_sizes", "PASS", f"{len(images)} images checked",
            "All images are within recommended file size limits.", "none"
        ))
    return results


def main():
    parser = argparse.ArgumentParser(description="Email HTML QA checker")
    parser.add_argument("--html-file", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--subject", default="")
    parser.add_argument("--preview-text", default="")
    parser.add_argument("--plain-text", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.html_file, "r", encoding="utf-8") as f:
        html_content = f.read()

    config = {}
    if os.path.exists(args.config):
        with open(args.config) as f:
            config = json.load(f)

    html_parser = EmailHTMLParser()
    html_parser.feed(html_content)

    all_results = []
    all_results += check_subject(args.subject)
    all_results += check_preview_text(args.preview_text)

    # Plain text version check
    if not args.plain_text or not args.plain_text.strip():
        all_results.append(run_check(
            "plain_text_version", "WARN", "empty",
            "No plain text version found. Some email clients and accessibility tools rely on it.",
            "marketo", "Add a plain text version in Marketo."
        ))
    else:
        all_results.append(run_check(
            "plain_text_version", "PASS", "present",
            "Plain text version is present.", "none"
        ))

    all_results += check_html_size(html_content)
    all_results += check_alt_text(html_parser.images)
    all_results += check_buttons(html_parser.buttons)
    all_results += check_links(html_parser.links)
    all_results += check_unsubscribe(html_parser.has_unsubscribe, html_parser.links)
    all_results += check_velocity_tokens(html_content)
    all_results += check_image_types(html_parser.images)
    all_results += check_text_image_ratio(html_parser.images, html_parser.text_parts)
    all_results += check_utm_params(html_parser.links, config)
    all_results += check_image_sizes(html_parser.images)

    passed = sum(1 for r in all_results if r["status"] == "PASS")
    warnings = sum(1 for r in all_results if r["status"] == "WARN")
    failures = sum(1 for r in all_results if r["status"] == "FAIL")

    output = {
        "html_checks": all_results,
        "http_links": extract_http_links(html_parser.links),
        "summary": {
            "total_checks": len(all_results),
            "passed": passed,
            "warnings": warnings,
            "failures": failures,
        }
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"QA complete: {passed} passed, {warnings} warnings, {failures} failures")
    print(f"Results written to {args.output}")


if __name__ == "__main__":
    main()
