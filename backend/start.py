"""Startup script that loads .env.local before starting uvicorn."""
import os
from pathlib import Path

# Load .env.local explicitly before anything else
env_file = Path(__file__).parent / ".env.local"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

import uvicorn
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
