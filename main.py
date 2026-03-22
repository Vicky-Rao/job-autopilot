"""
job-autopilot — entry point
Usage:
  python main.py add <url>       # Scrape job URL, generate cover letter, save as approved
  python main.py apply <job_id>  # Fill application form for a specific job
  python main.py apply-next      # Fill application for next approved job in queue
  python main.py simulate        # Run simulation with mock data
  python main.py review          # Review pending jobs (approve/reject)
  python main.py stats           # Show application stats
"""

import sys
import os
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
console = Console()


def cmd_add(url: str):
    """Scrape a job URL, generate cover letter, save directly as approved."""
    from discovery.url_scraper import scrape_job
    from generator.cover_letter import generate_cover_letter
    from tracker.db import init_db, upsert_job

    init_db()

    console.print(f"\n[cyan]Scraping:[/cyan] {url}")
    job_data = scrape_job(url)

    title = job_data["title"]
    company = job_data["company"]
    description = job_data["description"]

    console.print(f"[green]Found:[/green] {title} @ {company}")
    console.print("[cyan]Generating cover letter...[/cyan]")

    cover_letter = generate_cover_letter(title, company, description)

    job_record = {
        "id": str(uuid.uuid4()),
        "title": title,
        "company": company,
        "description": description,
        "salary_raw": None,
        "location": "Remote",
        "remote": 1,
        "url": url,
        "source": job_data.get("source", "manual"),
        "funding": None,
        "domain_tags": [],
        "score": None,
        "filter_reasons": [],
        "status": "approved",
        "cover_letter": cover_letter,
    }
    upsert_job(job_record)

    job_id = job_record["id"]
    console.print(f"\n[bold green]Saved![/bold green] Job ID: [yellow]{job_id}[/yellow]")
    console.print("\n[dim]Cover letter preview:[/dim]")
    console.print(cover_letter[:400] + ("..." if len(cover_letter) > 400 else ""))
    console.print(f"\nRun: [bold]python main.py apply {job_id}[/bold]")


def cmd_apply(job_id: str):
    """Open application form for a job, fill it, pause for review."""
    import asyncio
    from tracker.db import get_job_by_id, mark_applied

    job = get_job_by_id(job_id)
    if not job:
        console.print(f"[red]Job not found:[/red] {job_id}")
        return

    console.print(f"\n[cyan]Applying to:[/cyan] {job['title']} @ {job['company']}")
    cover_letter = job.get("cover_letter") or ""

    if not cover_letter:
        console.print("[yellow]No cover letter found — generating one now...[/yellow]")
        from generator.cover_letter import generate_cover_letter
        cover_letter = generate_cover_letter(job["title"], job["company"], job["description"])

    from applicator.form_filler import fill_application
    submitted = asyncio.run(fill_application(job, cover_letter))

    if submitted:
        mark_applied(job_id, cover_letter)
        console.print(f"\n[bold green]Applied![/bold green] Marked as applied in tracker.")
    else:
        console.print("\n[yellow]Not marked as applied — run again when ready.[/yellow]")


def cmd_apply_next():
    """Apply to the next approved job in the queue."""
    from tracker.db import get_approved_jobs

    jobs = get_approved_jobs()
    if not jobs:
        console.print("[yellow]No approved jobs in queue. Run 'python main.py add <url>' first.[/yellow]")
        return

    job = jobs[0]
    console.print(f"[dim]Queue: {len(jobs)} approved job(s). Taking first:[/dim]")
    cmd_apply(job["id"])


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "add":
        if len(sys.argv) < 3:
            console.print("[red]Usage:[/red] python main.py add <url>")
            return
        cmd_add(sys.argv[2])

    elif cmd == "apply":
        if len(sys.argv) < 3:
            console.print("[red]Usage:[/red] python main.py apply <job_id>")
            return
        cmd_apply(sys.argv[2])

    elif cmd == "apply-next":
        cmd_apply_next()

    elif cmd == "simulate":
        from tests.simulate import run_simulation
        run_simulation()

    elif cmd == "review":
        from review import run_review
        run_review()

    elif cmd == "stats":
        from tracker.db import init_db, get_stats
        init_db()
        stats = get_stats()
        console.print("\n[bold]Application Stats:[/bold]")
        for status, count in stats.items():
            console.print(f"  {status}: {count}")

    elif cmd == "run":
        console.print("[yellow]Live run not yet implemented — use 'add <url>' to queue jobs manually.[/yellow]")

    else:
        console.print("""
[bold cyan]job-autopilot[/bold cyan]

Commands:
  [green]add <url>[/green]        Scrape job URL, generate cover letter, save as approved
  [green]apply <job_id>[/green]   Fill application form and pause for review
  [green]apply-next[/green]       Apply to next job in the approved queue
  [green]simulate[/green]         Run with mock data to test the pipeline
  [green]review[/green]           Review and approve/reject queued jobs
  [green]stats[/green]            Show application stats
""")


if __name__ == "__main__":
    main()
