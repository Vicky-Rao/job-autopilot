"""
Interactive review CLI — shows filtered jobs and lets you approve/reject before applying.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from tracker.db import get_pending_review, mark_approved, mark_rejected

console = Console()


def show_job_detail(job: dict):
    console.print(Panel(
        f"[bold]{job['title']}[/bold] @ [cyan]{job['company']}[/cyan]\n\n"
        f"[dim]Source:[/dim] {job['source']}  |  [dim]Score:[/dim] {job['score']}/100\n"
        f"[dim]Salary:[/dim] {job.get('salary_raw') or 'Not listed'}  |  "
        f"[dim]Remote:[/dim] {'Yes' if job['remote'] else 'No'}\n"
        f"[dim]Funding:[/dim] {job.get('funding') or 'Unknown'}\n\n"
        f"[dim]URL:[/dim] {job['url']}\n\n"
        f"[green]Why it passed:[/green]\n" +
        "\n".join(f"  • {r}" for r in (eval(job.get('filter_reasons', '[]')) or [])),
        title="Job Details",
        border_style="blue"
    ))


def run_review():
    jobs = get_pending_review()

    if not jobs:
        console.print("[yellow]No jobs pending review.[/yellow]")
        return

    console.print(f"\n[bold green]{len(jobs)} jobs ready for review[/bold green]\n")

    # Summary table
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("#", width=4)
    table.add_column("Score", width=7)
    table.add_column("Role", width=30)
    table.add_column("Company", width=20)
    table.add_column("Salary", width=12)
    table.add_column("Source", width=12)

    for i, job in enumerate(jobs, 1):
        table.add_row(
            str(i),
            f"{job['score']}/100",
            job["title"],
            job["company"],
            job.get("salary_raw") or "—",
            job["source"]
        )

    console.print(table)
    console.print()

    # Review each job
    for i, job in enumerate(jobs, 1):
        console.print(f"\n[bold]Job {i}/{len(jobs)}[/bold]")
        show_job_detail(job)

        while True:
            choice = console.input(
                "[bold]Apply? ([green]y[/green]es / [red]n[/red]o / [yellow]s[/yellow]kip all) → [/bold]"
            ).strip().lower()

            if choice == "y":
                mark_approved(job["id"])
                console.print("[green]✓ Approved — will generate cover letter and apply[/green]")
                break
            elif choice == "n":
                reason = console.input("Reason (optional, press Enter to skip): ").strip()
                mark_rejected(job["id"], reason)
                console.print("[red]✗ Rejected[/red]")
                break
            elif choice == "s":
                console.print("[yellow]Skipping remaining jobs.[/yellow]")
                return
            else:
                console.print("Please enter y, n, or s")

    console.print("\n[bold green]Review complete.[/bold green]")
