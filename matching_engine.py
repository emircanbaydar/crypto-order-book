from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from order import Order, OrderSide, OrderType
from order_book import OrderBook


@dataclass(frozen=True)
class Trade:
    """Gerçekleşmiş bir alım-satım işleminin kaydı."""

    buy_order_id: UUID
    sell_order_id: UUID
    price: Decimal
    quantity: Decimal
    trade_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MatchingEngine:
    """Yeni emirleri deftere eklemeden önce karşı emirlerle eşleştirir."""

    def __init__(self) -> None:
        self.order_book = OrderBook()

    def process_order(self, order: Order) -> list[Trade]:
        """Emri eşleştirir; dolmayan limit kısmını deftere ekler."""
        if not isinstance(order, Order):
            raise TypeError("order, Order türünde olmalıdır.")

        remaining_quantity = order.quantity
        trades: list[Trade] = []
        is_buy = order.side is OrderSide.BUY
        is_market = order.order_type is OrderType.MARKET
        opposite_orders = (
            self.order_book.asks if is_buy else self.order_book.bids
        )

        while remaining_quantity > Decimal("0") and opposite_orders:
            resting_order = opposite_orders[0]
            if is_market:
                crosses = True
            elif order.price is None:
                raise ValueError("LIMIT emri için price zorunludur.")
            else:
                crosses = (
                    order.price >= resting_order.price
                    if is_buy
                    else order.price <= resting_order.price
                )
            if not crosses:
                break

            traded_quantity = min(remaining_quantity, resting_order.quantity)
            trades.append(
                Trade(
                    buy_order_id=order.order_id if is_buy else resting_order.order_id,
                    sell_order_id=resting_order.order_id if is_buy else order.order_id,
                    price=resting_order.price,
                    quantity=traded_quantity,
                )
            )

            remaining_quantity -= traded_quantity
            resting_order.quantity -= traded_quantity

            if resting_order.quantity == Decimal("0"):
                removed = self.order_book.cancel_order(str(resting_order.order_id))
                if not removed:
                    raise RuntimeError(
                        "Eşleşmesi tamamlanan emir defterden kaldırılamadı."
                    )

        if remaining_quantity > Decimal("0") and not is_market:
            # Kalan miktarı ayrı bir emir nesnesi olarak deftere koyar; böylece
            # çağıranın gönderdiği Order nesnesinin miktarı değiştirilmez.
            if order.price is None:
                raise ValueError("LIMIT emri için price zorunludur.")
            self.order_book.add_order(
                Order(
                    side=order.side,
                    price=order.price,
                    quantity=remaining_quantity,
                    order_id=order.order_id,
                    timestamp=order.timestamp,
                    order_type=OrderType.LIMIT,
                )
            )

        return trades


if __name__ == "__main__":
    engine = MatchingEngine()
    resting_sells = [
        Order(
            side=OrderSide.SELL,
            price=Decimal("102.00"),
            quantity=Decimal("2"),
        ),
        Order(
            side=OrderSide.SELL,
            price=Decimal("103.50"),
            quantity=Decimal("3"),
        ),
    ]
    for sell_order in resting_sells:
        engine.order_book.add_order(sell_order)

    market_buy = Order(
        side=OrderSide.BUY,
        quantity=Decimal("4"),
        order_type=OrderType.MARKET,
    )
    trades = engine.process_order(market_buy)

    print("Market BUY işlemleri:")
    for index, trade in enumerate(trades, start=1):
        print(
            f"{index}. işlem: {trade.price} TL'den "
            f"{trade.quantity} adet (Trade ID: {trade.trade_id})"
        )

    print("\nİşlem sonrası emir defteri (103.50 TL'den 1 adet satış kalmalı):")
    print(engine.order_book)