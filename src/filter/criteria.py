"""
Filter engine — matches job listings against Vicky's target criteria.
"""

import re
from dataclasses import dataclass
from typing import Optional

DOMAIN_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "defi", "decentralized finance",
    "web3", "blockchain", "crypto", "nft", "dao", "protocol", "saas", "b2b saas",
    "fintech", "trading", "dex", "perp", "perpetual", "zkSync", "layer 2", "l2"
]

ROLE_KEYWORDS = [
    "senior product designer", "lead product designer", "principal product designer",
    "senior ux designer", "lead ux designer", "head of design", "product design lead"
]

REJECT_KEYWORDS = [
    "junior", "entry level", "intern", "graphic designer", "visual designer only",
    "on-site only", "in-office", "no remote", "must relocate"
]

SALARY_PATTERNS = [
    r"(\d+)\s*-\s*(\d+)\s*lpa",
    r"(\d+)\s*lpa",
    r"(\d+)\s*-\s*(\d+)\s*lakhs?",
    r"\$(\d+)[kK]\s*-\s*\$?(\d+)[kK]",
]


@dataclass
class Job:
    id: str
    title: str
    company: str
    description: str
    salary_raw: Optional[str]
    location: str
    remote: bool
    url: str
    source: str
    funding: Optional[str] = None
    domain_tags: list = None

    def __post_init__(self):
        if self.domain_tags is None:
            self.domain_tags = []


@dataclass
class FilterResult:
    job: Job
    passed: bool
    score: int  # 0-100
    reasons: list[str]
    rejections: list[str]


def extract_salary_lpa(salary_raw: str) -> Optional[float]:
    """Extract minimum salary in LPA from raw salary string."""
    if not salary_raw:
        return None
    text = salary_raw.lower()
    for pattern in SALARY_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))
    return None


def detect_domains(text: str) -> list[str]:
    """Detect matching domains from job text."""
    text_lower = text.lower()
    return [kw for kw in DOMAIN_KEYWORDS if kw in text_lower]


def filter_job(job: Job, min_salary_lpa: float = 30.0) -> FilterResult:
    """
    Evaluate a job listing against target criteria.
    Returns a FilterResult with score and pass/fail.
    """
    reasons = []
    rejections = []
    score = 0

    title_lower = job.title.lower()
    desc_lower = job.description.lower()
    combined = f"{title_lower} {desc_lower} {job.location.lower()}"

    # Hard reject: bad role keywords
    for kw in REJECT_KEYWORDS:
        if kw in combined:
            rejections.append(f"Rejected keyword: '{kw}'")
            return FilterResult(job=job, passed=False, score=0, reasons=[], rejections=rejections)

    # Role match (required)
    role_match = any(kw in combined for kw in ROLE_KEYWORDS)
    if role_match:
        score += 30
        reasons.append("Role title matches Senior/Lead Product Designer")
    else:
        rejections.append("Role title does not match target keywords")
        return FilterResult(job=job, passed=False, score=score, reasons=reasons, rejections=rejections)

    # Remote check (required)
    if job.remote or "remote" in combined:
        score += 20
        reasons.append("Remote position confirmed")
    else:
        rejections.append("Not a remote position")
        return FilterResult(job=job, passed=False, score=score, reasons=reasons, rejections=rejections)

    # Domain match (required — at least one)
    domains = detect_domains(combined)
    if domains:
        score += 25
        reasons.append(f"Domain match: {', '.join(set(domains))}")
    else:
        rejections.append("No target domain keywords found (AI, DeFi, Web3, SaaS)")
        return FilterResult(job=job, passed=False, score=score, reasons=reasons, rejections=rejections)

    # Salary check (soft — salary often not listed)
    salary = extract_salary_lpa(job.salary_raw)
    if salary is not None:
        if salary >= min_salary_lpa:
            score += 15
            reasons.append(f"Salary {salary} LPA meets minimum {min_salary_lpa} LPA")
        else:
            rejections.append(f"Salary {salary} LPA below minimum {min_salary_lpa} LPA")
            return FilterResult(job=job, passed=False, score=score, reasons=reasons, rejections=rejections)
    else:
        score += 5  # partial credit — salary unknown, don't hard reject
        reasons.append("Salary not listed — will assess during application")

    # Funding bonus
    if job.funding:
        score += 10
        reasons.append(f"Funding info: {job.funding}")

    return FilterResult(
        job=job,
        passed=True,
        score=min(score, 100),
        reasons=reasons,
        rejections=rejections
    )
