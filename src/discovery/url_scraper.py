"""
Job URL scraper — extracts job title, company, and description from any job posting URL.
Handles YC Work at a Startup (JSON-LD), and generic job boards via BeautifulSoup.
"""

import json
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Tags that are unlikely to contain job description content
NOISE_TAGS = {"script", "style", "nav", "header", "footer", "aside", "form", "noscript"}


def scrape_job(url: str) -> dict:
    """
    Scrape a job posting URL and return structured job data.

    Returns:
        dict with keys: title, company, description, url, source
    """
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    domain = urlparse(url).netloc.replace("www.", "")

    # YC Work at a Startup — rich JSON-LD
    if "workatastartup.com" in domain:
        return _scrape_yc(soup, url, domain)

    # Generic fallback
    return _scrape_generic(soup, url, domain)


def _scrape_yc(soup: BeautifulSoup, url: str, domain: str) -> dict:
    """Parse YC Work at a Startup job pages via JSON-LD or structured HTML."""
    # Try JSON-LD first
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                data = data[0]
            if data.get("@type") == "JobPosting":
                return {
                    "title": data.get("title", "Unknown Role"),
                    "company": data.get("hiringOrganization", {}).get("name", _extract_company_generic(soup, url)),
                    "description": BeautifulSoup(data.get("description", ""), "html.parser").get_text(" ", strip=True),
                    "url": url,
                    "source": domain,
                }
        except (json.JSONDecodeError, AttributeError):
            continue

    # Fallback to generic for YC
    return _scrape_generic(soup, url, domain)


def _scrape_generic(soup: BeautifulSoup, url: str, domain: str) -> dict:
    title = _extract_title(soup)
    company = _extract_company_generic(soup, url)
    description = _extract_description(soup)
    return {
        "title": title,
        "company": company,
        "description": description,
        "url": url,
        "source": domain,
    }


def _extract_title(soup: BeautifulSoup) -> str:
    # Priority: <h1> → og:title → <title>
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)

    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()

    title_tag = soup.find("title")
    if title_tag:
        # Strip common suffixes like " | Company" or " - Company"
        text = title_tag.get_text(strip=True)
        return re.split(r"\s*[\|–\-]\s*", text)[0].strip()

    return "Unknown Role"


def _extract_company_generic(soup: BeautifulSoup, url: str) -> str:
    # og:site_name
    og = soup.find("meta", property="og:site_name")
    if og and og.get("content"):
        return og["content"].strip()

    # <title> often has "Role | Company" or "Role at Company"
    title_tag = soup.find("title")
    if title_tag:
        text = title_tag.get_text(strip=True)
        at_match = re.search(r"\bat\b\s+(.+?)(?:\s*[\|–\-]|$)", text, re.IGNORECASE)
        if at_match:
            return at_match.group(1).strip()
        parts = re.split(r"\s*[\|–\-]\s*", text)
        if len(parts) >= 2:
            return parts[-1].strip()

    # Fall back to domain
    domain = urlparse(url).netloc.replace("www.", "")
    return domain.split(".")[0].title()


def _extract_description(soup: BeautifulSoup) -> str:
    """Extract the main job description text, preferring structured content blocks."""
    # Remove noise tags in-place
    for tag in soup(NOISE_TAGS):
        tag.decompose()

    # Try common job description containers
    candidates = []
    for selector in [
        "article",
        "[class*='job-description']",
        "[class*='description']",
        "[class*='content']",
        "[id*='description']",
        "main",
        ".job-details",
        ".posting-description",
    ]:
        els = soup.select(selector)
        for el in els:
            text = el.get_text(" ", strip=True)
            if len(text) > 200:
                candidates.append(text)

    if candidates:
        # Return longest candidate (most complete description)
        return max(candidates, key=len)[:8000]

    # Last resort: all body text
    body = soup.find("body")
    if body:
        return body.get_text(" ", strip=True)[:8000]

    return soup.get_text(" ", strip=True)[:8000]
