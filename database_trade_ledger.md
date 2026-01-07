# Project 2: Trade Settlement Ledger

## The Fintech Problem
Your prop trading desk executes hundreds of trades daily. Settlement (T+1, T+2) requires tracking each trade's lifecycle: executed → confirmed → settled. Operations needs a ledger to reconcile positions and flag settlement failures. As TPM, you're owning the Trade Lifecycle Tracking system.

## What You'll Learn
- Relational database design (tables, relationships, constraints)
- SQL CRUD operations
- Data flow through a trading system
- State machines for financial workflows

## TPM Context
You're coordinating between:
- **Trading Desk** – needs real-time position visibility
- **Middle Office** – reconciles trades, catches breaks
- **Back Office** – manages settlement with counterparties

Your job: Design the data model, define the trade lifecycle, ensure data integrity.

---

## Project Spec

### Build a Trade Settlement Ledger
Create a SQLite database that:
1. Stores trades with full lifecycle tracking
2. Supports status transitions (executed → confirmed → settled/failed)
3. Provides queries for position reconciliation and settlement monitoring

### Data Flow
```
Trade Execution ──► [Ledger DB] ──► Confirmation ──► Settlement
       │                │                              │
       ▼                ▼                              ▼
  Insert trade    Update status              Mark settled/failed
```

### Trade Lifecycle State Machine
```
EXECUTED ──► CONFIRMED ──► SETTLED
    │            │
    ▼            ▼
 CANCELLED    FAILED
```

---

## Step-by-Step Build

### Step 1: Design the Schema
```sql
-- schema.sql

-- Core trade record
CREATE TABLE trades (
    trade_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT CHECK(side IN ('BUY', 'SELL')) NOT NULL,
    quantity INTEGER NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    notional DECIMAL(15,2) GENERATED ALWAYS AS (quantity * price) STORED,
    counterparty TEXT NOT NULL,
    status TEXT DEFAULT 'EXECUTED' CHECK(status IN ('EXECUTED', 'CONFIRMED', 'SETTLED', 'FAILED', 'CANCELLED')),
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP,
    settled_at TIMESTAMP,
    settlement_date DATE,
    error_reason TEXT
);

-- Audit trail for all status changes
CREATE TABLE trade_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT REFERENCES trades(trade_id),
    old_status TEXT,
    new_status TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- Index for common queries
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_settlement_date ON trades(settlement_date);
CREATE INDEX idx_trades_symbol ON trades(symbol);
```

### Step 2: Build the Python Interface
```python
# trade_ledger.py
import sqlite3
from datetime import datetime, timedelta
from typing import Optional
import uuid

class TradeLedger:
    def __init__(self, db_path: str = "trades.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
    
    def _init_schema(self):
        """Initialize database schema."""
        with open("schema.sql", "r") as f:
            self.conn.executescript(f.read())
        self.conn.commit()
    
    def insert_trade(self, symbol: str, side: str, quantity: int, 
                     price: float, counterparty: str, settlement_days: int = 1) -> str:
        """Insert new trade, returns trade_id."""
        trade_id = f"TRD-{uuid.uuid4().hex[:8].upper()}"
        settlement_date = (datetime.now() + timedelta(days=settlement_days)).date()
        
        self.conn.execute("""
            INSERT INTO trades (trade_id, symbol, side, quantity, price, counterparty, settlement_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (trade_id, symbol, side, quantity, price, counterparty, settlement_date))
        
        # Log the event
        self._log_event(trade_id, None, "EXECUTED", "SYSTEM", "Trade created")
        self.conn.commit()
        return trade_id
    
    def update_status(self, trade_id: str, new_status: str, 
                      changed_by: str, notes: Optional[str] = None) -> bool:
        """Update trade status with validation."""
        # Get current status
        cursor = self.conn.execute(
            "SELECT status FROM trades WHERE trade_id = ?", (trade_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Trade {trade_id} not found")
        
        old_status = row["status"]
        
        # Validate state transition
        valid_transitions = {
            "EXECUTED": ["CONFIRMED", "CANCELLED"],
            "CONFIRMED": ["SETTLED", "FAILED"],
            "SETTLED": [],  # Terminal state
            "FAILED": ["CONFIRMED"],  # Can retry
            "CANCELLED": []  # Terminal state
        }
        
        if new_status not in valid_transitions.get(old_status, []):
            raise ValueError(f"Invalid transition: {old_status} → {new_status}")
        
        # Update trade
        timestamp_field = {
            "CONFIRMED": "confirmed_at",
            "SETTLED": "settled_at"
        }.get(new_status)
        
        if timestamp_field:
            self.conn.execute(f"""
                UPDATE trades SET status = ?, {timestamp_field} = CURRENT_TIMESTAMP
                WHERE trade_id = ?
            """, (new_status, trade_id))
        else:
            self.conn.execute(
                "UPDATE trades SET status = ? WHERE trade_id = ?",
                (new_status, trade_id)
            )
        
        self._log_event(trade_id, old_status, new_status, changed_by, notes)
        self.conn.commit()
        return True
    
    def _log_event(self, trade_id: str, old_status: Optional[str], 
                   new_status: str, changed_by: str, notes: Optional[str]):
        """Log status change to audit trail."""
        self.conn.execute("""
            INSERT INTO trade_events (trade_id, old_status, new_status, changed_by, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (trade_id, old_status, new_status, changed_by, notes))
    
    # === QUERY METHODS (What Ops/Middle Office Needs) ===
    
    def get_pending_settlements(self, date: Optional[str] = None) -> list:
        """Get trades pending settlement for a given date."""
        if date is None:
            date = datetime.now().date().isoformat()
        
        cursor = self.conn.execute("""
            SELECT trade_id, symbol, side, quantity, price, notional, counterparty, status
            FROM trades
            WHERE settlement_date = ? AND status IN ('EXECUTED', 'CONFIRMED')
            ORDER BY notional DESC
        """, (date,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_position_by_symbol(self) -> list:
        """Get net position per symbol (settled trades only)."""
        cursor = self.conn.execute("""
            SELECT 
                symbol,
                SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) as net_quantity,
                SUM(CASE WHEN side = 'BUY' THEN notional ELSE -notional END) as net_notional
            FROM trades
            WHERE status = 'SETTLED'
            GROUP BY symbol
            ORDER BY ABS(net_notional) DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_failed_trades(self) -> list:
        """Get all failed trades for investigation."""
        cursor = self.conn.execute("""
            SELECT trade_id, symbol, side, quantity, price, counterparty, 
                   executed_at, error_reason
            FROM trades
            WHERE status = 'FAILED'
            ORDER BY executed_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_trade_history(self, trade_id: str) -> list:
        """Get full audit trail for a trade."""
        cursor = self.conn.execute("""
            SELECT old_status, new_status, changed_by, changed_at, notes
            FROM trade_events
            WHERE trade_id = ?
            ORDER BY changed_at
        """, (trade_id,))
        return [dict(row) for row in cursor.fetchall()]


# === DEMO / TEST ===
if __name__ == "__main__":
    ledger = TradeLedger("demo_trades.db")
    
    # Simulate trading day
    print("=== Inserting Trades ===")
    t1 = ledger.insert_trade("AAPL", "BUY", 100, 185.50, "GOLDMAN")
    t2 = ledger.insert_trade("AAPL", "SELL", 50, 186.00, "MORGAN")
    t3 = ledger.insert_trade("TSLA", "BUY", 200, 245.00, "CITADEL")
    print(f"Created: {t1}, {t2}, {t3}")
    
    # Move through lifecycle
    print("\n=== Processing Confirmations ===")
    ledger.update_status(t1, "CONFIRMED", "MIDDLE_OFFICE", "Matched with counterparty")
    ledger.update_status(t2, "CONFIRMED", "MIDDLE_OFFICE", "Matched with counterparty")
    ledger.update_status(t3, "CONFIRMED", "MIDDLE_OFFICE", "Matched with counterparty")
    
    # Settle some, fail one
    print("\n=== Settlement ===")
    ledger.update_status(t1, "SETTLED", "BACK_OFFICE")
    ledger.update_status(t2, "SETTLED", "BACK_OFFICE")
    ledger.update_status(t3, "FAILED", "BACK_OFFICE", "Counterparty DK'd the trade")
    
    # Reports
    print("\n=== Position Report ===")
    for pos in ledger.get_position_by_symbol():
        print(f"  {pos['symbol']}: {pos['net_quantity']} shares, ${pos['net_notional']:.2f} notional")
    
    print("\n=== Failed Trades ===")
    for trade in ledger.get_failed_trades():
        print(f"  {trade['trade_id']}: {trade['symbol']} {trade['quantity']}@{trade['price']}")
    
    print("\n=== Trade Audit Trail ===")
    for event in ledger.get_trade_history(t3):
        print(f"  {event['old_status']} → {event['new_status']} by {event['changed_by']}")
```

### Step 3: Run It
```bash
# Create schema file first, then run
python trade_ledger.py
```

---

## Key Concepts to Internalize

### Database Design Principles
| Principle | Application | Why It Matters |
|-----------|-------------|----------------|
| Primary Key | `trade_id` unique identifier | Prevents duplicates, enables lookups |
| Foreign Key | `trade_events.trade_id` → `trades` | Maintains referential integrity |
| CHECK Constraint | `side IN ('BUY', 'SELL')` | Enforces valid values at DB level |
| Index | On `status`, `settlement_date` | Fast queries for common operations |
| Audit Table | `trade_events` | Compliance, debugging, accountability |

### State Machine Design
Financial workflows almost always follow state machines. TPM must understand:
- **Valid transitions** (what moves are allowed?)
- **Terminal states** (SETTLED, CANCELLED can't change)
- **Retry logic** (FAILED → CONFIRMED is allowed for re-attempts)

### SQL Queries TPM Should Know
```sql
-- Daily settlement volume
SELECT settlement_date, COUNT(*), SUM(notional) 
FROM trades WHERE status = 'SETTLED' 
GROUP BY settlement_date;

-- Counterparty exposure
SELECT counterparty, SUM(notional) 
FROM trades WHERE status IN ('EXECUTED', 'CONFIRMED')
GROUP BY counterparty ORDER BY 2 DESC;

-- Avg time to settlement
SELECT AVG(julianday(settled_at) - julianday(executed_at)) * 24 as avg_hours
FROM trades WHERE status = 'SETTLED';
```

---

## TPM Discussion Questions

1. **Middle office reports duplicate trades in the system. How do you investigate?**
   - Query for trades with same symbol/qty/price/time within window
   - Check if de-duplication logic exists
   - Review trade capture process for root cause

2. **Back office wants to add a new status "PENDING_SETTLEMENT". What do you consider?**
   - Where does it fit in the state machine?
   - Which transitions lead to/from it?
   - What downstream systems need to know about it?
   - Schema migration plan for existing trades

3. **Compliance asks how long you retain trade data. What's your response?**
   - Check regulatory requirements (7 years typical for trading records)
   - Discuss archival strategy (cold storage vs. hot)
   - Audit trail retention separate from live data

---

## Extension Challenges
- [ ] Add counterparty table with credit limits
- [ ] Implement position limits (reject trade if exceeds threshold)
- [ ] Build a daily settlement report generator
- [ ] Add trade matching logic (auto-confirm if both sides agree)

---

## Time Estimate
- Schema + basic CRUD: 1.5 hours
- Query methods: 30 min
- Extensions: 1 hour each
