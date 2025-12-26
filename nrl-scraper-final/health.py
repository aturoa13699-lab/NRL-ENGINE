from fastapi import FastAPI
from datetime import datetime

app = FastAPI(title="nrl-scraper-health", version="1.0.0")
START = datetime.utcnow().isoformat() + "Z"


@app.get("/")
def root():
    return {"service": "nrl-scraper", "status": "ok", "start": START}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/ready")
def ready():
    return {"ready": True}
