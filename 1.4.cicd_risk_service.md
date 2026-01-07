# Project 4: Risk Calculation Service Deployment Pipeline

## The Fintech Problem
Your quant team built a VaR (Value at Risk) calculation service. It needs to run daily before market open (6 AM ET) with zero tolerance for errors—wrong risk numbers could cause regulatory issues or bad trading decisions. Currently, deployment is manual: someone SSHs into prod and pulls new code. Last week, a bad deploy caused the overnight risk run to fail. As TPM, you're implementing a proper CI/CD pipeline.

## What You'll Learn
- SDLC environments (Dev → QA → Prod)
- CI/CD pipeline stages and purpose
- Testing strategies for financial systems
- Deployment patterns (blue-green, canary)

## TPM Context
You're coordinating between:
- **Quant Team** – writes risk models, wants fast iteration
- **Risk Management** – needs reliable daily output, hates surprises
- **Compliance** – requires audit trail for all changes
- **DevOps/SRE** – owns infrastructure and deployment

Your job: Balance speed of delivery with reliability, ensure proper controls.

---

## SDLC Environments Explained

### The Three Environments
```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DEVELOPMENT (Dev)                                │
│  • Engineers build and test locally                                      │
│  • Connects to mock/sandbox data                                         │
│  • No real positions or PII                                              │
│  • Deploy anytime, break freely                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ Code passes local tests
┌─────────────────────────────────────────────────────────────────────────┐
│                         QA / STAGING                                     │
│  • Mirrors production setup                                              │
│  • Uses anonymized/synthetic production-like data                        │
│  • QA team runs test cases                                               │
│  • Performance testing happens here                                      │
│  • Deploy requires PR approval                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ QA sign-off + release approval
┌─────────────────────────────────────────────────────────────────────────┐
│                         PRODUCTION (Prod)                                │
│  • Real data, real users, real money                                     │
│  • Strict access controls                                                │
│  • All changes logged for audit                                          │
│  • Deploy only during approved windows                                   │
│  • Rollback plan required                                                │
└─────────────────────────────────────────────────────────────────────────┘
```

### Environment Comparison
| Aspect | Dev | QA/Staging | Prod |
|--------|-----|------------|------|
| Data | Mock/synthetic | Anonymized real | Real |
| Access | All engineers | Engineers + QA | Limited (SRE + on-call) |
| Deploy | Anytime | PR approval | Change window |
| Monitoring | Basic | Full | Full + alerting |
| Rollback | Not needed | Manual | Automated |

---

## CI/CD Pipeline Design

### Pipeline Stages
```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  Code   │───▶│  Build  │───▶│  Test   │───▶│ Deploy  │───▶│ Deploy  │
│  Push   │    │         │    │         │    │ Staging │    │  Prod   │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
     │              │              │              │              │
     │              │              │              │              │
     ▼              ▼              ▼              ▼              ▼
  Trigger       Compile        Unit tests     Smoke tests   Canary deploy
  on PR         Docker build   Integration    QA approval   Health checks
  to main       Lint/format    Coverage       Load tests    Full rollout
```

### What Happens at Each Stage

**1. Code Push (Trigger)**
- Developer opens PR to `main` branch
- Pipeline automatically triggered
- PR linked to Jira ticket for traceability

**2. Build**
- Install dependencies
- Compile code (if applicable)
- Build Docker image
- Run linting and formatting checks
- Fail fast if build breaks

**3. Test**
- **Unit tests:** Test individual functions (fast, run every commit)
- **Integration tests:** Test service with dependencies (DB, APIs)
- **Coverage check:** Require minimum 80% coverage
- **Regression tests:** Ensure old bugs don't return

**4. Deploy to Staging**
- Automated deploy on merge to `main`
- Run smoke tests (basic health checks)
- QA runs manual test cases
- Performance/load testing
- Security scan

**5. Deploy to Prod**
- Requires explicit approval (release manager or TPM)
- Canary deployment (10% traffic first)
- Monitor error rates and latency
- If healthy, roll out to 100%
- If issues, automatic rollback

---

## Build It: GitHub Actions Pipeline

### Project Structure
```
risk-service/
├── src/
│   └── var_calculator.py
├── tests/
│   └── test_var_calculator.py
├── Dockerfile
├── requirements.txt
├── .github/
│   └── workflows/
│       └── ci-cd.yml
└── README.md
```

### The Risk Calculator (Simple Example)
```python
# src/var_calculator.py
import numpy as np
from typing import List

def calculate_var(returns: List[float], confidence: float = 0.95) -> float:
    """
    Calculate Value at Risk using historical simulation.
    
    Args:
        returns: List of historical daily returns
        confidence: Confidence level (e.g., 0.95 for 95% VaR)
    
    Returns:
        VaR as a positive number representing potential loss
    """
    if not returns:
        raise ValueError("Returns list cannot be empty")
    
    if not 0 < confidence < 1:
        raise ValueError("Confidence must be between 0 and 1")
    
    sorted_returns = sorted(returns)
    index = int((1 - confidence) * len(sorted_returns))
    var = -sorted_returns[index]  # Negative because losses are negative returns
    
    return round(var, 6)

def calculate_portfolio_var(positions: dict, returns_matrix: dict, 
                            confidence: float = 0.95) -> dict:
    """
    Calculate VaR for a portfolio of positions.
    
    Args:
        positions: {symbol: notional_value}
        returns_matrix: {symbol: [list of returns]}
        confidence: Confidence level
    
    Returns:
        {
            "portfolio_var": float,
            "component_var": {symbol: var},
            "confidence": float
        }
    """
    component_vars = {}
    portfolio_returns = []
    
    for symbol, notional in positions.items():
        if symbol not in returns_matrix:
            raise ValueError(f"No returns data for {symbol}")
        
        symbol_returns = returns_matrix[symbol]
        symbol_var = calculate_var(symbol_returns, confidence)
        component_vars[symbol] = symbol_var * notional
        
        # Weight returns by position size for portfolio calc
        weighted_returns = [r * notional for r in symbol_returns]
        if not portfolio_returns:
            portfolio_returns = weighted_returns
        else:
            portfolio_returns = [a + b for a, b in zip(portfolio_returns, weighted_returns)]
    
    # Normalize portfolio returns
    total_notional = sum(positions.values())
    portfolio_returns = [r / total_notional for r in portfolio_returns]
    
    return {
        "portfolio_var": calculate_var(portfolio_returns, confidence) * total_notional,
        "component_var": component_vars,
        "confidence": confidence,
        "total_notional": total_notional
    }
```

### Test File
```python
# tests/test_var_calculator.py
import pytest
from src.var_calculator import calculate_var, calculate_portfolio_var

class TestCalculateVar:
    """Unit tests for VaR calculation."""
    
    def test_basic_var_calculation(self):
        """Test VaR with known distribution."""
        # 100 returns: -10% to +10%
        returns = [i/1000 for i in range(-100, 100)]
        var = calculate_var(returns, confidence=0.95)
        # At 95%, we expect ~5th percentile = -9%
        assert 0.08 < var < 0.10
    
    def test_empty_returns_raises_error(self):
        """Empty returns should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            calculate_var([])
    
    def test_invalid_confidence_raises_error(self):
        """Confidence outside 0-1 should raise ValueError."""
        with pytest.raises(ValueError, match="between 0 and 1"):
            calculate_var([0.01, -0.01], confidence=1.5)
    
    def test_higher_confidence_higher_var(self):
        """99% VaR should be higher than 95% VaR."""
        returns = [i/1000 for i in range(-100, 100)]
        var_95 = calculate_var(returns, confidence=0.95)
        var_99 = calculate_var(returns, confidence=0.99)
        assert var_99 > var_95

class TestPortfolioVar:
    """Integration tests for portfolio VaR."""
    
    @pytest.fixture
    def sample_data(self):
        """Sample portfolio and returns data."""
        return {
            "positions": {"AAPL": 100000, "GOOGL": 50000},
            "returns_matrix": {
                "AAPL": [0.01, -0.02, 0.015, -0.01, 0.005] * 50,
                "GOOGL": [0.02, -0.015, 0.01, -0.025, 0.008] * 50
            }
        }
    
    def test_portfolio_var_returns_required_fields(self, sample_data):
        """Portfolio VaR should return all expected fields."""
        result = calculate_portfolio_var(
            sample_data["positions"],
            sample_data["returns_matrix"]
        )
        assert "portfolio_var" in result
        assert "component_var" in result
        assert "confidence" in result
        assert "total_notional" in result
    
    def test_missing_symbol_raises_error(self, sample_data):
        """Missing returns data should raise ValueError."""
        sample_data["positions"]["TSLA"] = 25000  # No TSLA in returns
        with pytest.raises(ValueError, match="No returns data"):
            calculate_portfolio_var(
                sample_data["positions"],
                sample_data["returns_matrix"]
            )

# Regression tests (bugs we've fixed before)
class TestRegressions:
    """Tests for previously identified bugs."""
    
    def test_var_handles_all_positive_returns(self):
        """Bug #123: VaR failed when all returns were positive."""
        returns = [0.01, 0.02, 0.03, 0.04, 0.05]
        var = calculate_var(returns, confidence=0.95)
        assert var < 0  # VaR is negative when no losses expected
```

### GitHub Actions Workflow
```yaml
# .github/workflows/ci-cd.yml
name: Risk Service CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # ============ BUILD & TEST ============
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov flake8

      - name: Lint code
        run: flake8 src/ tests/ --max-line-length=100

      - name: Run tests with coverage
        run: |
          pytest tests/ -v --cov=src --cov-report=xml --cov-fail-under=80

      - name: Upload coverage report
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml

  # ============ BUILD DOCKER IMAGE ============
  build-image:
    needs: build-and-test
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,prefix=
            type=raw,value=latest

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ============ DEPLOY TO STAGING ============
  deploy-staging:
    needs: build-image
    runs-on: ubuntu-latest
    environment: staging
    
    steps:
      - name: Deploy to Staging
        run: |
          echo "Deploying ${{ needs.build-image.outputs.image-tag }} to staging..."
          # In real world: kubectl apply, helm upgrade, or cloud-specific deploy
          
      - name: Run smoke tests
        run: |
          echo "Running smoke tests against staging..."
          # curl staging-endpoint/health
          # curl staging-endpoint/api/var -d '{"test": "data"}'
          
      - name: Notify QA
        run: |
          echo "Staging deployed. Ready for QA validation."
          # Slack notification, Jira update, etc.

  # ============ DEPLOY TO PROD ============
  deploy-prod:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval in GitHub
    
    steps:
      - name: Canary deployment (10%)
        run: |
          echo "Deploying canary to 10% of traffic..."
          # Gradual rollout logic
          
      - name: Monitor canary (5 min)
        run: |
          echo "Monitoring error rates and latency..."
          sleep 300  # In real world: check Datadog/Prometheus
          
      - name: Full rollout
        run: |
          echo "Canary healthy. Rolling out to 100%..."
          
      - name: Post-deploy validation
        run: |
          echo "Running production smoke tests..."
          # Verify critical endpoints
          
      - name: Create release tag
        run: |
          echo "Tagging release in Git..."
          # git tag v1.x.x
```

### Dockerfile
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Run as non-root user
RUN useradd -m appuser
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s \
  CMD python -c "from src.var_calculator import calculate_var; print('healthy')"

# Entry point
CMD ["python", "-m", "src.var_calculator"]
```

### Requirements
```
# requirements.txt
numpy>=1.24.0
pytest>=7.0.0
pytest-cov>=4.0.0
flake8>=6.0.0
```

---

## Key CI/CD Concepts

### Continuous Integration (CI)
**Goal:** Catch bugs early, keep main branch stable.

| Practice | Why It Matters |
|----------|----------------|
| Run tests on every PR | Catches bugs before merge |
| Require PR reviews | Second pair of eyes, knowledge sharing |
| Block merge on test failure | Protects main branch |
| Lint/format checks | Consistent code style |
| Coverage requirements | Ensures tests exist |

### Continuous Deployment (CD)
**Goal:** Reliable, repeatable deployments with minimal risk.

| Practice | Why It Matters |
|----------|----------------|
| Automated deploys | Eliminates human error |
| Environment promotion | Same artifact, different configs |
| Canary/blue-green | Limit blast radius of bugs |
| Automated rollback | Fast recovery |
| Audit trail | Compliance, debugging |

### Deployment Patterns

**Blue-Green:**
```
[Blue - Current] ◄── 100% traffic
[Green - New]    ◄── 0% traffic

After validation:
[Blue - Old]     ◄── 0% traffic  
[Green - New]    ◄── 100% traffic
```

**Canary:**
```
[Current] ◄── 90% traffic
[Canary]  ◄── 10% traffic

If healthy after X minutes:
[Current] ◄── 0% traffic
[New]     ◄── 100% traffic
```

---

## TPM Discussion Questions

1. **Quant team wants to deploy model changes daily. Risk says monthly is safer. How do you resolve?**
   - Propose: More frequent deploys with better testing, not less frequent
   - Show data: Smaller changes = easier rollback, lower risk
   - Compromise: Deploy to shadow mode first, compare outputs before go-live

2. **A prod deploy causes VaR to be 50% higher than expected. What's your incident process?**
   - Immediate: Rollback to previous version
   - Communication: Alert risk management, compliance
   - Root cause: What changed? Test gap? Data issue?
   - Prevention: Add regression test for this scenario

3. **Compliance asks for proof that code was tested before reaching production. What do you provide?**
   - GitHub Actions logs showing test runs
   - Code coverage reports
   - PR approval records
   - Deployment audit trail
   - Suggest: Automated compliance reports

4. **Engineering wants to skip staging for "small" changes. Your response?**
   - Define "small" objectively (lines of code? files changed?)
   - Risk: "Small" changes often cause big problems
   - Compromise: Fast-track path with extra automated tests, but still hits staging
   - Never skip for anything touching calculations

---

## Metrics TPM Should Track

| Metric | Target | Why |
|--------|--------|-----|
| Deployment frequency | Daily+ | Faster feedback loops |
| Lead time (commit → prod) | <1 day | Agility |
| Change failure rate | <5% | Quality |
| Mean time to recovery (MTTR) | <1 hour | Resilience |
| Test coverage | >80% | Confidence |
| Build time | <10 min | Developer productivity |

---

## Extension Challenges
- [ ] Add Slack notifications for deploy status
- [ ] Implement database migration step in pipeline
- [ ] Add performance benchmarking (fail if VaR calc >100ms)
- [ ] Set up staging environment with Terraform
- [ ] Add security scanning (Snyk, Trivy)

---

## Time Estimate
- Read and understand pipeline: 1 hour
- Set up GitHub Actions for your own project: 2 hours
- Explain SDLC/CI-CD to interviewer: 30 min practice
