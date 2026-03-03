"""
FastAPI webhook server.
Receives POST /webhook/signal from TradingView.
Returns 200 immediately; analysis runs in background.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Header
from fastapi.responses import JSONResponse

from config.settings import WEBHOOK_SECRET_TOKEN
from storage.database import init_db
from webhooks.models import TradingViewSignal
from webhooks.signal_store import process_signal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized")
    yield


app = FastAPI(
    title="AI Investment Advisor — Webhook Server",
    description="Receives TradingView/LuxAlgo signals and triggers Claude analysis",
    version="1.0.0",
    lifespan=lifespan,
)


def _verify_token(x_webhook_token: str | None) -> None:
    if not x_webhook_token or x_webhook_token != WEBHOOK_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing webhook token")


@app.post("/webhook/signal")
async def receive_signal(
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_token: str | None = Header(default=None),
):
    """
    Main webhook endpoint.
    TradingView POSTs here when an alert fires.

    Required header: X-Webhook-Token: <your secret>
    Body: JSON matching TradingViewSignal schema (unknown fields accepted)
    """
    _verify_token(x_webhook_token)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    try:
        signal = TradingViewSignal(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Signal validation error: {e}")

    # Schedule processing in background — respond immediately
    background_tasks.add_task(process_signal, signal)

    logger.info(f"Webhook received: {signal.ticker} / {signal.signal_type} / {signal.timeframe}")
    return JSONResponse({"status": "accepted", "ticker": signal.ticker})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"service": "AI Investment Advisor", "endpoints": ["/webhook/signal", "/health"]}
