import logging
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, model_validator

from engine_worker import EngineWorker
from matching_engine import Trade
from order import Order, OrderSide, OrderType
from order_book import OrderBook


logger = logging.getLogger(__name__)
INDEX_HTML_PATH = Path(__file__).with_name("index.html")


class CreateOrderRequest(BaseModel):
    """REST API üzerinden alınan emir bilgileri."""

    model_config = ConfigDict(extra="forbid")

    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = None

    @model_validator(mode="after")
    def validate_order_values(self) -> "CreateOrderRequest":
        if not self.quantity.is_finite() or self.quantity <= Decimal("0"):
            raise ValueError("quantity sıfırdan büyük ve sonlu olmalıdır.")

        if self.order_type is OrderType.LIMIT and self.price is None:
            raise ValueError("LIMIT emri için price zorunludur.")
        if self.price is not None and (
            not self.price.is_finite() or self.price <= Decimal("0")
        ):
            raise ValueError("price sıfırdan büyük ve sonlu olmalıdır.")
        return self


def _order_book_snapshot(order_book: OrderBook) -> dict[str, object]:
    def aggregate_levels(orders: list[Order]) -> list[dict[str, object]]:
        levels: dict[Decimal, tuple[Decimal, int]] = {}
        for order in orders:
            if order.price is None:
                continue
            quantity, order_count = levels.get(
                order.price, (Decimal("0"), 0)
            )
            levels[order.price] = (quantity + order.quantity, order_count + 1)

        return [
            {
                "price": str(price),
                "quantity": str(quantity),
                "order_count": order_count,
            }
            for price, (quantity, order_count) in levels.items()
        ]

    best_bid = order_book.get_best_bid()
    best_ask = order_book.get_best_ask()
    spread = order_book.get_spread()
    return {
        "best_bid": str(best_bid) if best_bid is not None else None,
        "best_ask": str(best_ask) if best_ask is not None else None,
        "spread": str(spread) if spread is not None else None,
        "bids": aggregate_levels(order_book.bids),
        "asks": aggregate_levels(order_book.asks),
    }


def _trade_payload(trade: Trade) -> dict[str, str]:
    return {
        "trade_id": str(trade.trade_id),
        "buy_order_id": str(trade.buy_order_id),
        "sell_order_id": str(trade.sell_order_id),
        "price": str(trade.price),
        "quantity": str(trade.quantity),
        "timestamp": trade.timestamp.isoformat(),
    }


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    worker = EngineWorker(
        on_processed=lambda order, trades: _publish_order_update(
            application, order, trades
        )
    )
    application.state.engine_worker = worker
    worker.start()
    try:
        yield
    finally:
        await worker.stop()


app = FastAPI(title="Crypto Order Book Engine", lifespan=lifespan)
websocket_clients: list[WebSocket] = []


async def _broadcast(payload: dict[str, object]) -> None:
    disconnected: list[WebSocket] = []
    for client in websocket_clients:
        try:
            await client.send_json(payload)
        except (WebSocketDisconnect, RuntimeError):
            disconnected.append(client)
        except Exception:
            logger.exception("WebSocket istemcisine yayın yapılamadı.")
            disconnected.append(client)

    for client in disconnected:
        if client in websocket_clients:
            websocket_clients.remove(client)


async def _publish_order_update(
    application: FastAPI,
    _order: Order,
    trades: list[Trade],
) -> None:
    worker: EngineWorker = application.state.engine_worker
    if trades:
        await _broadcast(
            {
                "type": "trades",
                "payload": [_trade_payload(trade) for trade in trades],
            }
        )
    await _broadcast(
        {
            "type": "orderbook_update",
            "payload": _order_book_snapshot(worker.matching_engine.order_book),
        }
    )


def _get_worker() -> EngineWorker:
    worker = getattr(app.state, "engine_worker", None)
    if worker is None:
        raise HTTPException(status_code=503, detail="Matching engine hazır değil.")
    return worker


@app.post("/api/orders", status_code=202)
async def create_order(request: CreateOrderRequest) -> dict[str, str]:
    order = Order(
        side=request.side,
        order_type=request.order_type,
        price=request.price,
        quantity=request.quantity,
    )
    await _get_worker().submit_order(order)
    return {"status": "queued", "order_id": str(order.order_id)}


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse(INDEX_HTML_PATH, media_type="text/html")


@app.get("/api/orderbook")
async def get_order_book() -> dict[str, object]:
    worker = _get_worker()
    return _order_book_snapshot(worker.matching_engine.order_book)


@app.websocket("/ws")
async def order_book_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    websocket_clients.append(websocket)

    worker = getattr(app.state, "engine_worker", None)
    if worker is not None:
        await websocket.send_json(
            {
                "type": "orderbook_snapshot",
                "payload": _order_book_snapshot(worker.matching_engine.order_book),
            }
        )

    try:
        while True:
            # Bağlantıyı canlı tutar; yayınlar server → client yönünde yapılır.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in websocket_clients:
            websocket_clients.remove(websocket)