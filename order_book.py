from decimal import Decimal
from typing import List, Optional

from order import Order, OrderSide


class OrderBook:
    """Alış ve satış emirlerini fiyat-zaman önceliğine göre tutar."""

    def __init__(self) -> None:
        self.bids: List[Order] = []
        self.asks: List[Order] = []

    def add_order(self, order: Order) -> None:
        """Emri yönüne göre, fiyat ve zaman önceliğini koruyarak ekler."""
        if not isinstance(order, Order):
            raise TypeError("order, Order türünde olmalıdır.")

        if any(
            existing.order_id == order.order_id
            for existing in self.bids + self.asks
        ):
            raise ValueError(f"Bu order_id zaten defterde: {order.order_id}")

        orders = self.bids if order.side is OrderSide.BUY else self.asks
        insert_at = len(orders)

        for index, existing in enumerate(orders):
            better_price = (
                order.price > existing.price
                if order.side is OrderSide.BUY
                else order.price < existing.price
            )
            same_price_earlier_time = (
                order.price == existing.price
                and order.timestamp < existing.timestamp
            )
            if better_price or same_price_earlier_time:
                insert_at = index
                break

        orders.insert(insert_at, order)

    def cancel_order(self, order_id: str) -> bool:
        """Kimliği eşleşen ilk emri siler; silindiyse True döndürür."""
        for orders in (self.bids, self.asks):
            for index, order in enumerate(orders):
                if str(order.order_id) == order_id:
                    del orders[index]
                    return True
        return False

    def get_best_bid(self) -> Optional[Decimal]:
        """En yüksek alış fiyatını, alış yoksa None döndürür."""
        return self.bids[0].price if self.bids else None

    def get_best_ask(self) -> Optional[Decimal]:
        """En düşük satış fiyatını, satış yoksa None döndürür."""
        return self.asks[0].price if self.asks else None

    def get_spread(self) -> Optional[Decimal]:
        """İki tarafta da emir varsa en iyi satış-alış farkını döndürür."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid is None or best_ask is None:
            return None
        return best_ask - best_bid

    def __str__(self) -> str:
        bid_lines = [
            f"  {order.price} x {order.quantity} (ID: {order.order_id})"
            for order in self.bids
        ]
        ask_lines = [
            f"  {order.price} x {order.quantity} (ID: {order.order_id})"
            for order in self.asks
        ]
        bids = "\n".join(bid_lines) if bid_lines else "  (boş)"
        asks = "\n".join(ask_lines) if ask_lines else "  (boş)"
        return f"Alış emirleri (bids):\n{bids}\nSatış emirleri (asks):\n{asks}"


if __name__ == "__main__":
    book = OrderBook()

    buy_orders = [
        Order(OrderSide.BUY, Decimal("99.50"), Decimal("2")),
        Order(OrderSide.BUY, Decimal("101.00"), Decimal("1.5")),
        Order(OrderSide.BUY, Decimal("100.25"), Decimal("3")),
    ]
    sell_orders = [
        Order(OrderSide.SELL, Decimal("102.00"), Decimal("2")),
        Order(OrderSide.SELL, Decimal("103.50"), Decimal("1")),
        Order(OrderSide.SELL, Decimal("102.75"), Decimal("4")),
    ]

    for order in buy_orders + sell_orders:
        book.add_order(order)

    print("Emir defterinin ilk hali:")
    print(book)
    print(f"\nEn iyi alış (best bid): {book.get_best_bid()}")
    print(f"En iyi satış (best ask): {book.get_best_ask()}")
    print(f"Makas (spread): {book.get_spread()}")

    cancelled = book.cancel_order(str(buy_orders[1].order_id))
    print(f"\nİptal edilen emir bulundu mu? {'Evet' if cancelled else 'Hayır'}")
    print("İptal sonrası emir defteri:")
    print(book)