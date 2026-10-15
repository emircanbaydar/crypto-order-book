from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class OrderSide(Enum):
    """Emrin alış mı satış mı olduğunu belirtir."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Emrin limit mi yoksa piyasa emri mi olduğunu belirtir."""

    LIMIT = "LIMIT"
    MARKET = "MARKET"


@dataclass(init=False)
class Order:
    """Emir defterine gönderilebilecek bir alış veya satış emri."""

    side: OrderSide
    price: Optional[Decimal]
    quantity: Decimal
    order_id: UUID
    timestamp: datetime
    order_type: OrderType

    def __init__(
        self,
        side: OrderSide,
        price: Optional[Decimal] = None,
        quantity: Optional[Decimal] = None,
        order_id: Optional[UUID] = None,
        timestamp: Optional[datetime] = None,
        order_type: OrderType = OrderType.LIMIT,
    ) -> None:
        self.side = side
        self.price = price
        if quantity is None:
            raise TypeError("quantity, Decimal türünde verilmelidir.")
        self.quantity = quantity
        self.order_id = order_id if order_id is not None else uuid4()
        self.timestamp = (
            timestamp if timestamp is not None else datetime.now(timezone.utc)
        )
        self.order_type = order_type
        self.__post_init__()

    def __post_init__(self) -> None:
        if not isinstance(self.side, OrderSide):
            raise TypeError("side, OrderSide.BUY veya OrderSide.SELL olmalıdır.")

        if not isinstance(self.order_type, OrderType):
            raise TypeError("order_type, OrderType.LIMIT veya OrderType.MARKET olmalıdır.")

        if self.order_type is OrderType.LIMIT and self.price is None:
            raise ValueError("LIMIT emri için price zorunludur.")

        if self.price is not None:
            self._validate_positive_decimal("price", self.price)
        self._validate_positive_decimal("quantity", self.quantity)

        if not isinstance(self.order_id, UUID):
            raise TypeError("order_id, UUID türünde olmalıdır.")
        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp, datetime türünde olmalıdır.")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp saat dilimi bilgisi içermelidir.")

    @staticmethod
    def _validate_positive_decimal(name: str, value: Decimal) -> None:
        if not isinstance(value, Decimal):
            raise TypeError(f"{name}, Decimal türünde olmalıdır; float kullanmayın.")
        if not value.is_finite() or value <= Decimal("0"):
            raise ValueError(f"{name}, sıfırdan büyük ve sonlu bir değer olmalıdır.")


if __name__ == "__main__":
    buy_order = Order(
        side=OrderSide.BUY,
        price=Decimal("102.50"),
        quantity=Decimal("3"),
    )
    sell_order = Order(
        side=OrderSide.SELL,
        price=Decimal("103.00"),
        quantity=Decimal("2"),
    )

    print(buy_order)
    print(sell_order)