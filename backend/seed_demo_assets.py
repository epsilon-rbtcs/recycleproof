"""Idempotently seed the immutable fictional PDFs under demo-assets/seed/."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from app.demo_storage import ensure_demo_seed_assets

if __name__ == "__main__":
    provider = ensure_demo_seed_assets()
    print(f"Synthetic demo evidence is ready in {provider} storage under demo-assets/seed/.")
    if provider == "local":
        print("AWS S3 is not connected; this is local development storage only.")
