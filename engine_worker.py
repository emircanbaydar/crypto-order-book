import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Awaitable, Callable, Optional

from matching_engine import MatchingEngine, Trade
from order import Order, OrderSide, OrderType


logger = logging.getLogger(__name__)


class EngineWorker:
    """Kuyruktaki emirleri tek tüketici üzerinden sırayla işler."""

    def __init__(
        self,
        on_processed: Optional[Callable[[Order, list[Trade]], Awaitable[None]]] = None,
    ) -> None:
        self.matching_engine = MatchingEngine()
        self.queue: asyncio.Queue[Optional[Order]] = asyncio.Queue()
        self._consumer_task: Optional[asyncio.Task[None]] = None
        self._stopping = False
        self._stop_lock = asyncio.Lock()
        self._on_processed = on_processed

    async def submit_order(self, order: Order) -> None:
        """Emri işlenmek üzere FIFO kuyruğuna ekler."""
        if not isinstance(order, Order):
            raise TypeError("order, Order türünde olmalıdır.")
        if self._stopping:
            raise RuntimeError("Durdurulmakta olan worker yeni emir kabul etmez.")
        if self._consumer_task is None or self._consumer_task.done():
            raise RuntimeError("Emir göndermeden önce worker.start() çağrılmalıdır.")

        await self.queue.put(order)
        logger.info(
            "Kuyruğa eklendi: side=%s type=%s quantity=%s price=%s order_id=%s at=%s",
            order.side.value,
            order.order_type.value,
            order.quantity,
            order.price,
            order.order_id,
            datetime.now(timezone.utc).isoformat(),
        )

    def start(self) -> None:
        """Arka planda tek bir emir tüketicisi başlatır."""
        if self._stopping:
            raise RuntimeError("Durdurulmuş worker yeniden başlatılamaz.")
        if self._consumer_task is not None and not self._consumer_task.done():
            raise RuntimeError("Worker zaten çalışıyor.")

        self._consumer_task = asyncio.create_task(
            self._consume_orders(),
            name="matching-engine-consumer",
        )
        logger.info("Matching engine worker başlatıldı.")

    async def stop(self) -> None:
        """Kuyruğu boşaltıp tüketiciyi sentinel ile güvenli şekilde durdurur."""
        async with self._stop_lock:
            if self._consumer_task is None:
                return
            if self._consumer_task.done():
                await self._consumer_task
                return

            self._stopping = True
            await self.queue.join()
            await self.queue.put(None)
            await self._consumer_task
            logger.info("Matching engine worker güvenli şekilde durduruldu.")

    async def _consume_orders(self) -> None:
        while True:
            order = await self.queue.get()
            try:
                if order is None:
                    return

                logger.info(
                    "Emir işleniyor: order_id=%s side=%s type=%s",
                    order.order_id,
                    order.side.value,
                    order.order_type.value,
                )
                trades = self.matching_engine.process_order(order)
                if self._on_processed is not None:
                    await self._on_processed(order, trades)
                if trades:
                    for trade in trades:
                        print(
                            "EŞLEŞME: "
                            f"{trade.quantity} adet, {trade.price} TL "
                            f"(buy={trade.buy_order_id}, "
                            f"sell={trade.sell_order_id}, "
                            f"trade={trade.trade_id})"
                        )
                else:
                    print(f"EŞLEŞME YOK: emir={order.order_id}")
            except Exception:
                logger.exception("Emir işlenirken hata oluştu: order_id=%s", order.order_id)
            finally:
                self.queue.task_done()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    worker = EngineWorker()
    worker.start()

    async def submit_after_delay(order: Order, delay: float) -> None:
        await asyncio.sleep(delay)
        await worker.submit_order(order)

    participants = [
        (
            "Satıcı 1",
            Order(
                side=OrderSide.SELL,
                price=Decimal("102.00"),
                quantity=Decimal("2"),
                order_type=OrderType.LIMIT,
            ),
            0.01,
        ),
        (
            "Alıcı 1",
            Order(
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                order_type=OrderType.MARKET,
            ),
            0.02,
        ),
        (
            "Alıcı 2",
            Order(
                side=OrderSide.BUY,
                price=Decimal("103.00"),
                quantity=Decimal("2"),
                order_type=OrderType.LIMIT,
            ),
            0.03,
        ),
        (
            "Satıcı 2",
            Order(
                side=OrderSide.SELL,
                quantity=Decimal("1"),
                order_type=OrderType.MARKET,
            ),
            0.04,
        ),
    ]

    async def participant_submit(name: str, order: Order, delay: float) -> None:
        logger.info("%s emirini göndermeye hazırlanıyor: %s", name, order.order_id)
        await submit_after_delay(order, delay)
        logger.info("%s emri kuyruğa gönderdi: %s", name, order.order_id)

    await asyncio.gather(
        *(
            participant_submit(name, order, delay)
            for name, order, delay in participants
        )
    )

    await worker.queue.join()
    print("\nTüm kuyruk işleri tamamlandı. Son emir defteri:")
    print(worker.matching_engine.order_book)
    await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())