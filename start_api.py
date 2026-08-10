#!/usr/bin/env python3
import uvicorn
import os

if __name__ == "__main__":
    reload_enabled = os.getenv("RELOAD", "false").lower() == "true"
    
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=8000,
        reload=reload_enabled,
        log_level="info"
    )
