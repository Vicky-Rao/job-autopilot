"""
job-autopilot — entry point
Usage:
  python main.py simulate   # Run simulation with mock data
  python main.py review     # Review pending jobs (approve/reject)
  python main.py run        # Full live run (discover → filter → queue for review)
  python main.py stats      # Show application stats
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
console = Console()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "simulate":
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
        console.print("[yellow]Live run not yet implemented — run 'simulate' first.[/yellow]")

    else:
        console.print("""
[bold cyan]job-autopilot[/bold cyan]

Commands:
  [green]simulate[/green]   Run with mock data to test the pipeline
  [green]review[/green]     Review and approve/reject queued jobs
  [green]stats[/green]      Show application stats
  [green]run[/green]        Live run (coming soon)
""")


if __name__ == "__main__":
    main()
