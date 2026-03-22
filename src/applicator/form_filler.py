"""
Playwright form filler — fills job application forms automatically.
Uses Claude to map form fields to candidate profile data, with heuristic fallbacks.
Strategy: LLM-guided field detection → fill → pause for human review and submit.
"""

import asyncio
import json
import os
from pathlib import Path

import anthropic
from playwright.async_api import async_playwright

PROFILE_PATH = Path(__file__).parent.parent.parent / "data" / "profile.json"
RESUME_PATH = Path(__file__).parent.parent.parent / "data" / "resumes" / "VickyRao_Resume.pdf"


def load_profile() -> dict:
    with open(PROFILE_PATH) as f:
        return json.load(f)


def _build_field_mapping_prompt(form_html: str, profile: dict, cover_letter: str) -> str:
    return f"""You are helping auto-fill a job application form.

CANDIDATE PROFILE:
- Name: {profile['name']}
- Email: {profile['email']}
- Phone: {profile['phone']}
- LinkedIn: {profile['linkedin']}
- Portfolio: {profile['portfolio']}
- Location: {profile['location']}
- Title: {profile['title']}
- Years of experience: {profile['years_of_experience']}

COVER LETTER (for textarea fields):
{cover_letter}

FORM HTML:
{form_html[:6000]}

Analyze the form and return a JSON array of field mappings. Each item must have:
- "selector": CSS selector to target the field (prefer id > name attribute > label text)
- "type": one of: text | email | tel | url | textarea | file | select
- "value": the value to fill in (for file type, use "RESUME")

Rules:
- Only include fields you can confidently map to the candidate's data
- For the cover letter / motivation / "why do you want..." textarea → use the cover letter text
- For resume/CV file upload → use type "file" with value "RESUME"
- Skip fields you cannot identify (checkboxes, unknown selects, etc.)
- Return ONLY valid JSON array, no markdown, no explanation.

Example output:
[
  {{"selector": "#applicant_name", "type": "text", "value": "Vicky Rao"}},
  {{"selector": "input[name='email']", "type": "email", "value": "vickyrao7024@gmail.com"}},
  {{"selector": "textarea[name='cover_letter']", "type": "textarea", "value": "...cover letter text..."}}
]"""


async def _llm_map_fields(form_html: str, profile: dict, cover_letter: str) -> list[dict]:
    """Ask Claude to map form fields to profile data. Returns list of field mappings."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = _build_field_mapping_prompt(form_html, profile, cover_letter)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = message.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


def _heuristic_map_fields(soup_inputs: list[dict], profile: dict, cover_letter: str) -> list[dict]:
    """
    Fallback heuristic field mapping when LLM fails.
    soup_inputs: list of dicts with keys: selector, type, name, placeholder, label
    """
    mappings = []
    for f in soup_inputs:
        name = (f.get("name") or "").lower()
        placeholder = (f.get("placeholder") or "").lower()
        label = (f.get("label") or "").lower()
        combined = f"{name} {placeholder} {label}"
        ftype = f.get("type", "text")

        value = None
        if ftype == "email" or "email" in combined:
            value = profile["email"]
        elif "phone" in combined or "tel" in combined:
            value = profile["phone"]
        elif "linkedin" in combined:
            value = profile["linkedin"]
        elif "portfolio" in combined or "website" in combined:
            value = profile["portfolio"]
        elif "name" in combined and "company" not in combined:
            value = profile["name"]
        elif "location" in combined or "city" in combined:
            value = profile["location"]
        elif ftype == "file" or "resume" in combined or "cv" in combined:
            value = "RESUME"
            ftype = "file"
        elif ftype == "textarea" or "cover" in combined or "motivation" in combined or "why" in combined:
            value = cover_letter
            ftype = "textarea"

        if value:
            mappings.append({"selector": f["selector"], "type": ftype, "value": value})

    return mappings


async def _extract_form_html(page) -> tuple[str, list[dict]]:
    """Extract form HTML and a flat list of input metadata for heuristic fallback."""
    # Get raw HTML of form elements
    form_html = await page.evaluate("""() => {
        const forms = document.querySelectorAll('form');
        if (forms.length > 0) {
            return Array.from(forms).map(f => f.outerHTML).join('\\n');
        }
        // If no <form> tags, grab all inputs
        const inputs = document.querySelectorAll('input, textarea, select');
        return Array.from(inputs).map(el => el.outerHTML).join('\\n');
    }""")

    # Flat input metadata for heuristic fallback
    inputs = await page.evaluate("""() => {
        const els = document.querySelectorAll('input, textarea, select');
        return Array.from(els).map(el => {
            const id = el.id ? '#' + el.id : null;
            const name = el.name ? `[name="${el.name}"]` : null;
            const selector = id || name || el.tagName.toLowerCase();
            // Find associated label
            let label = '';
            if (el.id) {
                const lbl = document.querySelector(`label[for="${el.id}"]`);
                if (lbl) label = lbl.innerText;
            }
            if (!label) {
                const parent = el.closest('label');
                if (parent) label = parent.innerText;
            }
            return {
                selector,
                type: el.type || el.tagName.toLowerCase(),
                name: el.name || '',
                placeholder: el.placeholder || '',
                label
            };
        }).filter(f => f.selector && f.type !== 'hidden' && f.type !== 'submit');
    }""")

    return form_html, inputs


async def fill_application(job: dict, cover_letter: str) -> bool:
    """
    Open the job application URL in a headed browser, fill the form, and pause for review.

    Returns True if user confirmed they submitted, False otherwise.
    """
    profile = load_profile()
    url = job.get("url", "")

    if not url:
        print("[error] Job has no URL — cannot open application form.")
        return False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=50)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"\nOpening: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)  # Let dynamic content settle

        form_html, inputs = await _extract_form_html(page)

        # Try LLM mapping first
        field_mappings = []
        try:
            print("Analyzing form fields with Claude...")
            field_mappings = await _llm_map_fields(form_html, profile, cover_letter)
            print(f"Claude mapped {len(field_mappings)} fields.")
        except Exception as e:
            print(f"LLM mapping failed ({e}), using heuristics...")
            field_mappings = _heuristic_map_fields(inputs, profile, cover_letter)
            print(f"Heuristic mapped {len(field_mappings)} fields.")

        if not field_mappings:
            print("[warning] No fields could be mapped. Browser is open — fill manually.")
        else:
            # Fill fields
            filled = 0
            for field in field_mappings:
                selector = field["selector"]
                ftype = field["type"]
                value = field["value"]

                try:
                    if ftype == "file":
                        if RESUME_PATH.exists():
                            await page.set_input_files(selector, str(RESUME_PATH))
                            print(f"  [resume] Uploaded {RESUME_PATH.name}")
                            filled += 1
                        else:
                            print(f"  [skip] Resume not found at {RESUME_PATH}")
                    elif ftype == "textarea":
                        await page.fill(selector, value)
                        print(f"  [textarea] Filled cover letter")
                        filled += 1
                    elif ftype == "select":
                        await page.select_option(selector, label=value)
                        print(f"  [select] {selector} = {value}")
                        filled += 1
                    else:
                        await page.fill(selector, value)
                        print(f"  [{ftype}] {selector} = {value[:60]}")
                        filled += 1
                except Exception as e:
                    print(f"  [skip] {selector}: {e}")

            print(f"\n{filled}/{len(field_mappings)} fields filled.")

        print("\n" + "=" * 60)
        print("REVIEW THE BROWSER — check all fields before submitting.")
        print("When you're happy, submit the form in the browser.")
        print("=" * 60)
        input("\nPress ENTER here after you've submitted (or to cancel): ")

        submitted = input("Did you submit successfully? (y/n): ").strip().lower() == "y"

        await browser.close()
        return submitted
