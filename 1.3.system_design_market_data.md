# Project 3: Real-Time Market Data Feed System

## The Fintech Problem
Your trading platform needs to display live prices to 10,000 concurrent users. Market data comes from multiple exchanges (NYSE, NASDAQ, CBOE). Users expect sub-second updates. The current system can't scale—latency spikes during market open cause user complaints. As TPM, you're leading the redesign of the Market Data Distribution system.

## What You'll Learn
- System design fundamentals (components, tradeoffs)
- Latency analysis and optimization
- Horizontal vs vertical scaling
- Caching strategies for real-time data

## TPM Context
You're coordinating between:
- **Market Data Team** – ingests feeds from exchanges
- **Platform Engineering** – serves data to frontend
- **Product** – wants new features (alerts, historical charts)
- **Infra/SRE** – owns reliability and cost

Your job: Design a system that scales, define SLAs, manage tradeoffs.

---

## The Design Exercise

### Requirements Gathering (Step 1 of Any System Design)

**Functional Requirements:**
- Display real-time prices for 5,000 symbols
- Support 10,000 concurrent users
- Price updates within 500ms of exchange timestamp
- Historical data for charting (1min, 5min, 1hr candles)

**Non-Functional Requirements:**
- 99.9% uptime (8.7 hours downtime/year max)
- P99 latency < 200ms for price queries
- Handle 3x normal load during market open/close

**TPM Clarifying Questions:**
- What's the current latency? (Baseline before optimization)
- Which symbols are most requested? (Pareto principle—probably 20% of symbols get 80% of traffic)
- Do all users need real-time, or can some tolerate 1-second delay?

---

## System Architecture

### High-Level Design
```
┌─────────────────────────────────────────────────────────────────────────┐
│                              EXCHANGES                                   │
│                    NYSE    NASDAQ    CBOE    IEX                        │
└────────────────────────┬────────────────────────────────────────────────┘
                         │ Raw market data feeds
                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      INGESTION LAYER                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │ Feed Handler │  │ Feed Handler │  │ Feed Handler │  (One per exchange)│
│  │    (NYSE)    │  │   (NASDAQ)   │  │    (CBOE)    │                   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                   │
│         └─────────────────┼─────────────────┘                           │
│                           ▼                                              │
│               ┌───────────────────────┐                                 │
│               │   Message Queue       │  (Kafka)                        │
│               │   topic: raw_quotes   │                                 │
│               └───────────┬───────────┘                                 │
└───────────────────────────┼─────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      PROCESSING LAYER                                    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              Quote Processor Service                             │    │
│  │  • Normalize data format across exchanges                        │    │
│  │  • Calculate NBBO (National Best Bid/Offer)                      │    │
│  │  • Compute candles (1m, 5m, 1hr)                                 │    │
│  │  • Publish to processed_quotes topic                             │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        CACHING LAYER                                     │
│         ┌──────────────────────────────────────┐                        │
│         │            Redis Cluster              │                        │
│         │  • Latest quote per symbol            │                        │
│         │  • Hot symbols in memory              │                        │
│         │  • TTL: 1 second (auto-expire stale)  │                        │
│         └──────────────────────────────────────┘                        │
│                           │                                              │
│         ┌─────────────────┼─────────────────┐                           │
│         ▼                 ▼                 ▼                            │
│   ┌──────────┐      ┌──────────┐      ┌──────────┐                      │
│   │ Redis 1  │      │ Redis 2  │      │ Redis 3  │  (Sharded by symbol) │
│   │ A-H      │      │ I-P      │      │ Q-Z      │                      │
│   └──────────┘      └──────────┘      └──────────┘                      │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        API LAYER                                         │
│              ┌─────────────────────────┐                                │
│              │     Load Balancer       │                                │
│              └───────────┬─────────────┘                                │
│         ┌────────────────┼────────────────┐                             │
│         ▼                ▼                ▼                              │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐                        │
│   │ API Pod  │     │ API Pod  │     │ API Pod  │  (Horizontally scaled) │
│   └──────────┘     └──────────┘     └──────────┘                        │
│         │                                                                │
│         │  REST: GET /quotes/{symbol}                                   │
│         │  WebSocket: subscribe to symbol updates                        │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLIENTS                                          │
│          Web App        Mobile App        Trading Bots                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Deep Dive: Key Components

### 1. Message Queue (Kafka)
**Why Kafka?**
- Handles high throughput (millions of messages/sec)
- Durable—won't lose data if consumers fall behind
- Multiple consumers can read same stream (processing, analytics, logging)

**TPM Considerations:**
- Partition by symbol for ordered processing
- Retention period (how long to keep data for replay?)
- Consumer lag monitoring (are processors keeping up?)

### 2. Caching Layer (Redis)
**Why Redis?**
- Sub-millisecond reads (in-memory)
- Built-in TTL for auto-expiration
- Pub/sub for real-time updates

**Caching Strategy:**
```
Key: quote:{symbol}
Value: {"bid": 185.50, "ask": 185.52, "last": 185.51, "ts": 1704567890}
TTL: 1 second

Key: candle:{symbol}:{interval}
Value: {"open": 185.00, "high": 186.00, "low": 184.50, "close": 185.51}
TTL: Based on interval (60s for 1m candle)
```

**TPM Considerations:**
- Cache hit ratio target (>95% ideal)
- What happens on cache miss? (Fall back to DB or reject?)
- Memory capacity planning

### 3. API Layer
**REST vs WebSocket:**
| Approach | Use Case | Tradeoff |
|----------|----------|----------|
| REST | One-time lookup, infrequent polling | Simple, stateless, higher latency |
| WebSocket | Real-time streaming | Lower latency, requires connection management |

**Recommendation:** WebSocket for active traders, REST for casual users.

---

## Latency Analysis

### Where Time Goes
```
Exchange → Feed Handler:     ~5ms   (network)
Feed Handler → Kafka:        ~2ms   (write)
Kafka → Processor:           ~5ms   (read + process)
Processor → Redis:           ~1ms   (write)
Redis → API:                 ~1ms   (read)
API → Client:               ~20ms   (network, varies by location)
                           -------
Total:                      ~34ms   (well under 200ms target)
```

### Latency Optimization Tactics
| Tactic | Impact | Complexity |
|--------|--------|------------|
| Co-locate services in same region | -10-50ms | Low |
| Use binary protocols (protobuf vs JSON) | -2-5ms | Medium |
| Connection pooling | -5-10ms | Low |
| Edge caching (CDN) for static data | -20-50ms | Medium |
| WebSocket instead of polling | -100ms+ | Medium |

---

## Scalability Analysis

### Vertical vs Horizontal Scaling
| Scaling Type | Approach | When to Use |
|--------------|----------|-------------|
| Vertical | Bigger machine (more CPU/RAM) | Database, single-threaded workloads |
| Horizontal | More machines | Stateless services (API, processors) |

### Capacity Math
```
Given:
- 10,000 concurrent users
- Each user subscribes to ~10 symbols
- Price updates every 100ms per active symbol

Calculate:
- Updates per second: 5,000 symbols × 10 updates/sec = 50,000 updates/sec
- WebSocket messages: 10,000 users × 10 symbols × 10/sec = 1,000,000 msg/sec

Scale requirements:
- Kafka: 3-5 brokers (easily handles 1M+ msg/sec)
- Redis: 3-node cluster (sharded by symbol)
- API Pods: ~20 pods (assuming 50K connections each)
```

### Handling Spikes (Market Open)
- **Auto-scaling:** Kubernetes HPA based on CPU/connection count
- **Rate limiting:** Cap subscriptions per user during peak
- **Graceful degradation:** Reduce update frequency from 100ms to 500ms

---

## Build a Minimal Version

```python
# mini_market_data.py
# Simulates the core flow: Publisher → Redis → Subscriber

import redis
import json
import time
import random
import threading

# Connect to Redis (install: pip install redis)
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

SYMBOLS = ["AAPL", "GOOGL", "TSLA", "MSFT", "AMZN"]

def simulate_exchange_feed():
    """Simulates exchange publishing price updates."""
    while True:
        for symbol in SYMBOLS:
            quote = {
                "symbol": symbol,
                "bid": round(random.uniform(100, 500), 2),
                "ask": round(random.uniform(100, 500), 2),
                "timestamp": time.time()
            }
            # Write to cache
            r.setex(f"quote:{symbol}", 1, json.dumps(quote))  # 1 sec TTL
            # Publish for real-time subscribers
            r.publish(f"quotes:{symbol}", json.dumps(quote))
        time.sleep(0.1)  # 100ms update interval

def get_quote(symbol: str) -> dict:
    """REST-style: Get latest quote from cache."""
    data = r.get(f"quote:{symbol}")
    if data:
        return json.loads(data)
    return {"error": "Quote not found or stale"}

def subscribe_quotes(symbols: list):
    """WebSocket-style: Subscribe to real-time updates."""
    pubsub = r.pubsub()
    for symbol in symbols:
        pubsub.subscribe(f"quotes:{symbol}")
    
    print(f"Subscribed to {symbols}")
    for message in pubsub.listen():
        if message["type"] == "message":
            quote = json.loads(message["data"])
            latency_ms = (time.time() - quote["timestamp"]) * 1000
            print(f"  {quote['symbol']}: {quote['bid']}/{quote['ask']} (latency: {latency_ms:.1f}ms)")

if __name__ == "__main__":
    # Start publisher in background
    publisher = threading.Thread(target=simulate_exchange_feed, daemon=True)
    publisher.start()
    
    time.sleep(0.5)  # Let some data populate
    
    # Demo REST-style lookup
    print("=== REST Query ===")
    print(get_quote("AAPL"))
    
    # Demo WebSocket-style subscription
    print("\n=== Real-Time Subscription (Ctrl+C to stop) ===")
    subscribe_quotes(["AAPL", "TSLA"])
```

---

## TPM Discussion Questions

1. **Product wants to add price alerts ("notify me when AAPL > $200"). How do you design it?**
   - New service consumes from Kafka
   - Maintains user alert rules in memory/Redis
   - Pushes notifications via separate channel (not same as price feed)
   - Consider: How many alerts per user? Alert fatigue?

2. **SRE reports Redis memory at 90%. What's your action plan?**
   - Immediate: Reduce TTL, evict cold symbols
   - Short-term: Add Redis nodes, re-shard
   - Long-term: Tiered caching (hot in Redis, warm in DB)

3. **Latency spikes to 2 seconds during market open. How do you debug?**
   - Check each layer: Kafka lag? Redis CPU? API pod count?
   - Look at metrics dashboards for the spike window
   - Was it sustained or one-time? (Thundering herd vs. incident)

4. **Engineering proposes removing Kafka to reduce latency. Your response?**
   - What's the actual latency contribution? (~5ms, minimal)
   - What do we lose? (Durability, replay, multiple consumers)
   - Tradeoff not worth it—focus optimization elsewhere

---

## Key Metrics TPM Should Track

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| P99 Latency (exchange → client) | <200ms | >500ms |
| Cache Hit Ratio | >95% | <90% |
| Kafka Consumer Lag | <1000 msgs | >10,000 msgs |
| WebSocket Connections | - | >80% capacity |
| Error Rate | <0.1% | >1% |

---

## Extension Challenges
- [ ] Add a circuit breaker for when exchange feed goes down
- [ ] Implement rate limiting per user
- [ ] Build a simple dashboard showing latency percentiles
- [ ] Design the historical data storage (time-series DB like InfluxDB/TimescaleDB)

---

## Time Estimate
- Read and understand architecture: 1 hour
- Build mini version: 1 hour
- Practice explaining to interviewer: 1 hour
