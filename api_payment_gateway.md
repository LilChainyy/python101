# Project 1: Payment Gateway Status API

## The Fintech Problem
Your company processes payments through multiple gateways (Stripe, Plaid, internal ledger). Operations needs a unified way to check payment status across systems. As TPM, you're scoping the MVP for a Payment Status Service.

## What You'll Learn
- HTTP methods and when to use each
- Request/response structure and error handling
- API authentication patterns
- Status codes and what they mean operationally

## TPM Context
In this project, you're the TPM coordinating between:
- **Payments Engineering** – building the API
- **Operations** – needs to query payment status quickly
- **Compliance** – requires audit logs of all status checks

Your job: Define requirements, understand technical tradeoffs, and ship an MVP.

---

## Project Spec

### Build a Payment Status Checker
Create a Python script that:
1. Calls a mock payment API to check transaction status
2. Handles different response scenarios (success, pending, failed)
3. Logs each request for audit trail

### Architecture
```
Operations User
      │
      ▼
[Your Script] ──GET /payments/{id}──► [Mock Payment API]
      │                                      │
      ▼                                      ▼
[Audit Log]                           {status, amount, timestamp}
```

---

## Step-by-Step Build

### Step 1: Set Up Mock API
We'll use JSONPlaceholder or build a simple Flask mock. For speed, use this mock structure:

```python
# mock_payment_api.py
from flask import Flask, jsonify

app = Flask(__name__)

# Simulated payment database
payments = {
    "txn_001": {"status": "completed", "amount": 150.00, "currency": "USD", "created_at": "2025-01-06T10:30:00Z"},
    "txn_002": {"status": "pending", "amount": 2500.00, "currency": "USD", "created_at": "2025-01-06T11:00:00Z"},
    "txn_003": {"status": "failed", "amount": 75.50, "currency": "USD", "error_code": "insufficient_funds"},
}

@app.route("/v1/payments/<payment_id>", methods=["GET"])
def get_payment(payment_id):
    if payment_id in payments:
        return jsonify({"id": payment_id, **payments[payment_id]}), 200
    return jsonify({"error": "payment_not_found", "message": f"No payment with id {payment_id}"}), 404

if __name__ == "__main__":
    app.run(port=5000)
```

### Step 2: Build the Client
```python
# payment_checker.py
import requests
import logging
from datetime import datetime

# Set up audit logging
logging.basicConfig(
    filename="payment_audit.log",
    level=logging.INFO,
    format="%(asctime)s | %(message)s"
)

BASE_URL = "http://localhost:5000/v1"

def check_payment_status(payment_id: str) -> dict:
    """
    Check payment status from gateway.
    Returns standardized response regardless of gateway.
    """
    endpoint = f"{BASE_URL}/payments/{payment_id}"
    
    try:
        response = requests.get(endpoint, timeout=5)
        
        # Log for audit trail
        logging.info(f"QUERY | payment_id={payment_id} | status_code={response.status_code}")
        
        # Handle response based on status code
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "payment_id": payment_id,
                "status": data["status"],
                "amount": data["amount"],
                "details": data
            }
        elif response.status_code == 404:
            return {
                "success": False,
                "payment_id": payment_id,
                "error": "Payment not found"
            }
        else:
            return {
                "success": False,
                "payment_id": payment_id,
                "error": f"Unexpected status: {response.status_code}"
            }
            
    except requests.exceptions.Timeout:
        logging.error(f"TIMEOUT | payment_id={payment_id}")
        return {"success": False, "error": "Gateway timeout"}
    except requests.exceptions.RequestException as e:
        logging.error(f"ERROR | payment_id={payment_id} | {str(e)}")
        return {"success": False, "error": str(e)}

# Test it
if __name__ == "__main__":
    test_ids = ["txn_001", "txn_002", "txn_003", "txn_999"]
    for txn_id in test_ids:
        result = check_payment_status(txn_id)
        print(f"{txn_id}: {result['status'] if result['success'] else result['error']}")
```

### Step 3: Run It
```bash
# Terminal 1: Start mock API
python mock_payment_api.py

# Terminal 2: Run checker
python payment_checker.py
```

---

## Key Concepts to Internalize

### HTTP Methods (TPM Must Know)
| Method | Use Case | Fintech Example |
|--------|----------|-----------------|
| GET | Read data | Check balance, get transaction |
| POST | Create resource | Initiate payment, create account |
| PUT | Update resource | Update user KYC info |
| DELETE | Remove resource | Cancel pending transfer |

### Status Codes (What Ops Will Ask About)
| Code | Meaning | TPM Action |
|------|---------|------------|
| 200 | Success | Normal flow |
| 400 | Bad request | Client bug, check payload |
| 401 | Unauthorized | Auth issue, check API keys |
| 404 | Not found | Invalid ID or data deleted |
| 429 | Rate limited | Need to implement backoff |
| 500 | Server error | Escalate to engineering |

### Authentication Patterns
```python
# API Key in header (common for internal services)
headers = {"Authorization": "Bearer sk_live_xxx"}

# Basic Auth (legacy systems)
requests.get(url, auth=("username", "password"))
```

---

## TPM Discussion Questions
Practice answering these as if in a TPM interview:

1. **Ops reports payments showing "pending" for 24+ hours. What's your debugging approach?**
   - Check API logs for the specific transaction
   - Verify downstream gateway status
   - Look for timeout patterns in audit log

2. **Engineering wants to add caching to reduce API calls. What questions do you ask?**
   - What's the cache TTL? (Stale payment status = bad)
   - How do we invalidate on status change?
   - What's the current latency vs. target?

3. **Compliance asks for all payment queries from last month. How do you deliver?**
   - Export from audit log
   - Discuss log retention policy
   - Propose structured logging format for future

---

## Extension Challenges
- [ ] Add retry logic with exponential backoff
- [ ] Support multiple payment gateways (Stripe + Plaid mock)
- [ ] Build a simple CLI interface for ops to use
- [ ] Add request timing to identify slow endpoints

---

## Time Estimate
- Initial build: 1 hour
- Extensions: 30 min each
