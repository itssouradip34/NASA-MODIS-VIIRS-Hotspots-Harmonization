"""
Pyro-Harmony Launcher.
Runs the high-performance FastAPI server with Uvicorn.
"""

import sys
import uvicorn
from src.api.config import settings

def main():
    print("=" * 70)
    print("  [FIRE] PYRO-HARMONY: NASA MODIS & VIIRS FIRE INTELLIGENCE PLATFORM")
    print("  2026 NASA Space Apps Challenge Prototype")
    print("=" * 70)
    print(f"  * Grounded in 5 Research Papers: Gao 2006, Weng 2017, Cheng 2020")
    print(f"  * Web Dashboard   : http://localhost:{settings.SERVER_PORT}")
    print(f"  * Interactive API : http://localhost:{settings.SERVER_PORT}/docs")
    print(f"  * API Keys Status : Protected / Hidden Server-Side")
    print("=" * 70)
    
    uvicorn.run(
        "src.api.main:app",
        host="127.0.0.1",
        port=settings.SERVER_PORT,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()
