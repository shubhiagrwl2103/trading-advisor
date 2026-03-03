"""
Start the webhook server with scheduler.

Usage:
    python -m scripts.start_webhook_server
    python -m scripts.start_webhook_server --port 8001 --host 0.0.0.0
"""

import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn

logging.basicConfig(level=logging.INFO)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the AI Advisor webhook server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev only)")
    args = parser.parse_args()

    print(f"Starting AI Advisor webhook server on {args.host}:{args.port}")
    uvicorn.run(
        "webhooks.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
