"""Optional localhost API over the shipped synthetic fixtures; the site needs none."""

from fastapi import FastAPI, HTTPException

from dayone.generate import ROOT
from dayone.normalize import normalize
from dayone.pipeline import run_pipeline
from dayone.schemas import DayOneBrief

app = FastAPI(title="Day One — SYNTHETIC record review", version="0.1.0")


def member_path(member_id: str):
    # Allowlist, never interpolate arbitrary path segments supplied by a client.
    valid = {f"SYN-{n:03d}" for n in range(1, 13)}
    if member_id not in valid:
        raise HTTPException(status_code=404, detail="Unknown synthetic member")
    path = ROOT / "data/synthetic" / f"{member_id}.json"
    if not path.exists():
        raise HTTPException(status_code=503, detail="Run make generate first")
    return path


@app.get("/health")
def health():
    return {"status": "ok", "synthetic": True, "mode": "offline"}


@app.get("/members")
def members():
    return [{"member_id": f"SYN-{n:03d}", "synthetic": True} for n in range(1, 13)]


@app.get("/members/{member_id}")
def record(member_id: str):
    return normalize(member_path(member_id))


@app.post("/members/{member_id}/brief", response_model=DayOneBrief)
def brief(member_id: str):
    return run_pipeline(member_path(member_id), llm_enabled=False).brief
