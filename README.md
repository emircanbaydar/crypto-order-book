# ⚡ Real-Time Crypto Order Book & Matching Engine

Yüksek frekanslı alım-satım işlemlerini simüle eden, bellek içi (in-memory) FIFO fiyat/zaman öncelikli limit ve piyasa (market) emir eşleştirme motoru.

## 🚀 Öne Çıkan Özellikler

- **Hassas Finansal Hesaplama:** `float` yuvarlama hatalarını önlemek için tüm fiyat ve bakiye mantığında `Decimal` aritmetiği.
- **Lock-Free Asenkron Kuyruk:** Yarış durumlarını (race condition) ve kilitlenmeleri (deadlock) önleyen `asyncio.Queue` tabanlı tek iş parçacıklı (single-threaded worker) tüketim mimarisi.
- **Çoklu Emir Tipleri:** 
  - `LIMIT`: Belirli fiyattan deftere asılan ve kısmi eşleşebilen (partial fill) emirler.
  - `MARKET`: Fiyat gözetmeksizin tahtayı en ucuz satıcıdan/en pahalı alıcıdan süpüren ve kalanı iptal eden (IoC) emirler.
- **Canlı WebSocket Akışı:** L2 tahta derinliği ve gerçekleşen işlemlerin (trades) bağlı web istemcilerine milisaniyelik canlı yayını.
- **İnteraktif Web UI:** Modern, anlık güncellenen derinlik tablosu ve emir gönderme paneli.

## 🛠️ Mimari Akış

```mermaid
graph TD
    Client[Web Browser / Bot] -->|REST API POST /orders| API[FastAPI Gateway]
    Client <-->|WebSocket /ws| Broadcast[Real-time Broadcaster]
    API -->|await queue.put| Queue[asyncio.Queue]
    Worker[Engine Worker] -->|await queue.get| Queue
    Worker -->|process_order| Engine[Matching Engine]
    Engine -->|Update / Match| OrderBook[(In-Memory L2 Order Book)]
    Engine -->|Emit Trades| Broadcast