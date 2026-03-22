# job-autopilot

Automated job application system for Senior Product Designer roles.

## Target Criteria
- **Role:** Senior Product Designer (4+ years)
- **Salary:** 30 LPA+
- **Type:** Remote only
- **Domains:** AI, DeFi, Web3, SaaS
- **Companies:** Well-funded startups + MNCs (remote)

## System Architecture

```
Job Discovery → Filter Engine → Cover Letter Gen → Application Engine → Tracker
     ↑                ↑                ↑                   ↑
  Scraper         Criteria         Claude API          Playwright
  (Wellfound,     (domain, pay,    (resume +           (form fill
   LinkedIn,       remote, etc.)   JD → letter)         + submit)
   Lever,
   Greenhouse)
```

## Modules

| Module | Path | Responsibility |
|--------|------|----------------|
| Discovery | `src/discovery/` | Scrape job listings from all sources |
| Filter | `src/filter/` | Match jobs against target criteria |
| Generator | `src/generator/` | Generate tailored cover letters via Claude API |
| Applicator | `src/applicator/` | Fill and submit applications via Playwright |
| Tracker | `src/tracker/` | Log and track all applications in SQLite |

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # Add your API keys
python main.py
```
