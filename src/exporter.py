"""
Exporter — dumps SQLite state to data/state.json and pushes to GitHub.
Called after every pipeline action so the dashboard stays in sync.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

from tracker.db import get_connection, init_db

STATE_PATH = Path(__file__).parent.parent / "data" / "state.json"
PROFILE_PATH = Path(__file__).parent.parent / "data" / "profile.json"


def export_state():
    """Export current DB state to state.json."""
    init_db()
    conn = get_connection()

    rows = conn.execute("SELECT * FROM jobs ORDER BY score DESC").fetchall()
    jobs = []
    for row in rows:
        d = dict(row)
        d["domain_tags"] = json.loads(d.get("domain_tags") or "[]")
        d["filter_reasons"] = json.loads(d.get("filter_reasons") or "[]")
        d["remote"] = bool(d["remote"])
        jobs.append(d)

    stats = {
        "total": len(jobs),
        "pending_review": sum(1 for j in jobs if j["status"] == "pending_review"),
        "approved": sum(1 for j in jobs if j["status"] == "approved"),
        "rejected": sum(1 for j in jobs if j["status"] == "rejected"),
        "applied": sum(1 for j in jobs if j["status"] == "applied"),
    }

    conn.close()

    with open(PROFILE_PATH) as f:
        profile_raw = json.load(f)

    profile = {
        "name": profile_raw.get("name", "Vicky Rao"),
        "portfolio": profile_raw.get("portfolio", ""),
        "resume_filename": Path(profile_raw.get("resume_path", "")).name,
        "email": profile_raw.get("email", ""),
        "linkedin": profile_raw.get("linkedin", ""),
    }

    state = {
        "last_updated": datetime.now().isoformat(),
        "profile": profile,
        "stats": stats,
        "jobs": jobs,
    }

    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, default=str)

    return state


def push_to_github(message: str = "bot: sync state.json"):
    """Commit and push state.json to GitHub."""
    repo_root = Path(__file__).parent.parent
    try:
        subprocess.run(["git", "add", "data/state.json"], cwd=repo_root, check=True)
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=repo_root
        )
        if result.returncode != 0:  # There are staged changes
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=repo_root, check=True
            )
            subprocess.run(["git", "push"], cwd=repo_root, check=True)
            print(f"✓ Pushed state.json to GitHub ({message})")
        else:
            print("✓ state.json unchanged — no push needed")
    except subprocess.CalledProcessError as e:
        print(f"⚠ GitHub push failed: {e}")


def sync(message: str = "bot: sync state.json"):
    """Export state and push to GitHub in one call."""
    export_state()
    push_to_github(message)
