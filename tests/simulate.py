"""
Simulation — runs the full pipeline with mock job data to verify the system works.
No real scraping, no real applications.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from rich.console import Console
from rich.panel import Panel

from filter.criteria import Job, filter_job
from tracker.db import init_db, upsert_job, get_pending_review, get_stats
from generator.cover_letter import generate_cover_letter
from exporter import sync

console = Console()

MOCK_JOBS = [
    Job(
        id="sim-001",
        title="Senior Product Designer",
        company="Drift Protocol",
        description="We're building the leading perpetual DEX on Solana. Looking for a Senior Product Designer to own the trading terminal UX, order flow design, and design system. Remote-first team, AI-powered features in roadmap. Series B funded.",
        salary_raw="35-45 LPA",
        location="Remote",
        remote=True,
        url="https://jobs.driftprotocol.com/senior-pd",
        source="simulation",
        funding="Series B",
        domain_tags=["defi", "perp", "saas"]
    ),
    Job(
        id="sim-002",
        title="Lead UX Designer — AI Products",
        company="Anthropic",
        description="Design AI-native products at Anthropic. Senior-level role focused on user research, interaction design for LLM interfaces. Remote US only.",
        salary_raw="$180k-$220k",
        location="Remote (US only)",
        remote=True,
        url="https://anthropic.com/careers/lead-ux",
        source="simulation",
        funding="Series D",
        domain_tags=["ai"]
    ),
    Job(
        id="sim-003",
        title="Junior UI Designer",
        company="Some Agency",
        description="Entry level graphic designer for marketing materials. On-site preferred.",
        salary_raw="8 LPA",
        location="Bangalore, on-site",
        remote=False,
        url="https://example.com/junior-ui",
        source="simulation",
        funding=None,
        domain_tags=[]
    ),
    Job(
        id="sim-004",
        title="Senior Product Designer — Web3",
        company="Coinbase",
        description="Join Coinbase to design consumer crypto products and DeFi experiences. Senior designer needed for wallet UX, DEX aggregator flows, and NFT marketplace. Fully remote, global.",
        salary_raw="40 LPA",
        location="Remote",
        remote=True,
        url="https://coinbase.com/careers/senior-pd",
        source="simulation",
        funding="Public (MNC)",
        domain_tags=["web3", "defi", "crypto"]
    ),
    Job(
        id="sim-005",
        title="Product Design Lead — B2B SaaS",
        company="Linear",
        description="Lead product design at Linear. Own design system, user research, and roadmap for our project management SaaS. AI features being shipped this quarter. Remote-first.",
        salary_raw=None,
        location="Remote",
        remote=True,
        url="https://linear.app/careers/design-lead",
        source="simulation",
        funding="Series B",
        domain_tags=["saas", "ai"]
    ),
    Job(
        id="sim-006",
        title="Senior Product Designer",
        company="Random Corp",
        description="Looking for a product designer for our e-commerce platform. Must relocate to Mumbai.",
        salary_raw="20 LPA",
        location="Mumbai, on-site",
        remote=False,
        url="https://example.com/random",
        source="simulation",
        funding=None,
        domain_tags=[]
    ),
]


def run_simulation():
    console.print(Panel(
        "[bold cyan]JOB AUTOPILOT — SIMULATION MODE[/bold cyan]\n"
        "Running full pipeline with mock data. No real applications will be sent.",
        border_style="cyan"
    ))

    # Step 1: Init DB
    console.print("\n[bold]Step 1: Initializing database...[/bold]")
    init_db()
    console.print("[green]✓ Database ready[/green]")

    # Step 2: Filter jobs
    console.print(f"\n[bold]Step 2: Filtering {len(MOCK_JOBS)} mock jobs...[/bold]")
    passed = []
    failed = []

    for job in MOCK_JOBS:
        result = filter_job(job, min_salary_lpa=30.0)
        if result.passed:
            passed.append(result)
            console.print(f"  [green]✓ PASS[/green] [{result.score}/100] {job.title} @ {job.company}")
            for r in result.reasons:
                console.print(f"       [dim]→ {r}[/dim]")
        else:
            failed.append(result)
            console.print(f"  [red]✗ FAIL[/red] {job.title} @ {job.company}")
            for r in result.rejections:
                console.print(f"       [dim]→ {r}[/dim]")

    console.print(f"\n  Passed: [green]{len(passed)}[/green] / Failed: [red]{len(failed)}[/red]")

    # Step 3: Save to DB
    console.print(f"\n[bold]Step 3: Saving {len(passed)} jobs to tracker...[/bold]")
    for result in passed:
        upsert_job({
            "id": result.job.id,
            "title": result.job.title,
            "company": result.job.company,
            "description": result.job.description,
            "salary_raw": result.job.salary_raw,
            "location": result.job.location,
            "remote": int(result.job.remote),
            "url": result.job.url,
            "source": result.job.source,
            "funding": result.job.funding,
            "domain_tags": result.job.domain_tags,
            "score": result.score,
            "filter_reasons": result.reasons,
        })
    console.print("[green]✓ Jobs saved[/green]")

    # Step 4: Show pending review
    console.print(f"\n[bold]Step 4: Jobs queued for your review:[/bold]")
    pending = get_pending_review()
    for j in pending:
        console.print(f"  • [{j['score']}/100] [cyan]{j['title']}[/cyan] @ {j['company']} — {j['url']}")

    # Step 5: Test cover letter generation (for top job)
    if pending and os.environ.get("ANTHROPIC_API_KEY"):
        top = pending[0]
        console.print(f"\n[bold]Step 5: Generating cover letter for top job ({top['company']})...[/bold]")
        try:
            letter = generate_cover_letter(top["title"], top["company"], top["description"])
            console.print(Panel(letter, title=f"Cover Letter — {top['company']}", border_style="green"))
        except Exception as e:
            console.print(f"[yellow]Cover letter generation skipped: {e}[/yellow]")
    else:
        console.print("\n[yellow]Step 5: Skipping cover letter test (no ANTHROPIC_API_KEY set)[/yellow]")

    # Summary
    stats = get_stats()
    console.print(Panel(
        f"[bold]Simulation complete.[/bold]\n\n"
        f"Discovered: {len(MOCK_JOBS)}  |  "
        f"Passed filter: [green]{len(passed)}[/green]  |  "
        f"Rejected: [red]{len(failed)}[/red]\n"
        f"Pending your review: [yellow]{stats['pending_review']}[/yellow]",
        title="Results",
        border_style="cyan"
    ))
    console.print("\nRun [bold]python main.py review[/bold] to approve/reject jobs before applying.\n")

    # Step 6: Sync to GitHub dashboard
    console.print("[bold]Step 6: Syncing state to GitHub...[/bold]")
    try:
        sync("bot: simulation run — sync state.json")
    except Exception as e:
        console.print(f"[yellow]GitHub sync skipped: {e}[/yellow]")


if __name__ == "__main__":
    run_simulation()
