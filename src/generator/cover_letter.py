"""
Cover letter generator — uses Claude API to write tailored cover letters.
"""

import os
import json
from pathlib import Path
import anthropic

PROFILE_PATH = Path(__file__).parent.parent.parent / "data" / "profile.json"


def load_profile() -> dict:
    with open(PROFILE_PATH) as f:
        return json.load(f)


def generate_cover_letter(job_title: str, company: str, job_description: str) -> str:
    """Generate a tailored cover letter for a specific job."""
    profile = load_profile()
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = f"""You are writing a cover letter for {profile['name']}, a {profile['title']}.

CANDIDATE PROFILE:
- {profile['years_of_experience']}+ years of experience
- Summary: {profile['summary']}
- Key achievements:
  * Shipped Perp DEX (zkSync) → $25M trading volume in 60 days, 70K+ signups
  * Reduced liquidation rates from 12% to 8%
  * Increased stop-loss adoption from 22% to 64%
  * 2.4x improvement in user retention
  * 50% MoM lead growth at Rentok
- Domain expertise: DeFi, Crypto, Trading Terminals, B2B SaaS, Perp DEX
- Tools: Figma, FigJam, Framer, After Effects
- Portfolio: {profile['portfolio']}

JOB DETAILS:
- Role: {job_title}
- Company: {company}
- Description: {job_description[:2000]}

Write a concise, punchy cover letter (3 short paragraphs max) that:
1. Opens with a specific hook referencing something real about the company/role
2. Connects Vicky's most relevant DeFi/crypto/SaaS experience to this role with concrete numbers
3. Closes with a clear call to action

Tone: Confident, direct, no corporate fluff. Write like a founder, not a job seeker.
Do NOT use "I am writing to express my interest" or similar clichés.
Output only the cover letter body — no subject line, no "Dear Hiring Manager" header."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text
