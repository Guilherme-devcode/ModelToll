# ModelToll

> **The intelligent AI gateway for the enterprise.**
> Intercept. Scrub. Route. Audit. Save.

ModelToll sits at the network level between your employees and every AI provider they use. It enforces data security policies, routes requests to approved cheaper models, and tracks every dollar saved — all without disrupting anyone's workflow.

---

## The Problem: Shadow AI

Every enterprise today has the same invisible crisis:

| Who | What's happening |
|-----|-----------------|
| Developers | Pasting proprietary code into ChatGPT |
| Designers | Subscribed to 3 different AI image tools on the company card |
| Product managers | Uploading customer data to AI summarizers |
| Finance | No idea what's being spent or where |
| Security | No visibility into what data left the building |
| Legal | Panic after the fact |

**Shadow AI is a $100B compliance and cost problem hiding in plain sight.**

---

## How ModelToll Works

```
Employee → [ChatGPT / Claude / Copilot / Any AI]
               ↓
          ModelToll Gateway
          ┌──────────────────────────┐
          │ 1. Intercept the request │
          │ 2. Detect sensitive data │
          │ 3. Scrub PII / secrets   │
          │ 4. Route to approved,    │
          │    cheaper model         │
          │ 5. Log for audit         │
          │ 6. Track cost savings    │
          └──────────────────────────┘
               ↓
          Approved LLM (cheaper)
               ↓
          Response → Employee
          (they see no difference)
```

---

## Architecture

```
modeltoll/
├── src/
│   ├── config/          # Pydantic settings (env-driven)
│   ├── scrubber/        # PII + secrets detection engine (Presidio + regex)
│   ├── router/          # Model routing + cost arbitrage
│   ├── audit/           # Async PostgreSQL audit logger
│   ├── proxy/           # FastAPI gateway + route handlers
│   └── dashboard/       # Admin REST API (cost, logs, analytics)
├── config/
│   ├── model_routing.json    # Source → target model map + cost data
│   └── custom_patterns.json  # Enterprise regex patterns (keys, CPF, CNPJ, …)
├── tests/
│   ├── unit/            # Scrubber, router, gateway unit tests
│   └── integration/     # End-to-end proxy flow tests
└── docker/
    └── Dockerfile
```

---

## Quick Start

### 1. Clone & configure

```bash
git clone <repo>
cd ModelToll
cp .env.example .env
# Edit .env with your settings
```

### 2. Run with Docker Compose

```bash
docker compose up -d
```

This starts:
- **ModelToll gateway** on port `8080`
- **PostgreSQL** on port `5432`
- **Redis** on port `6379`

### 3. Point your AI client to ModelToll

Instead of `https://api.openai.com`, use `http://localhost:8080`.

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-openai-key",
    base_url="http://localhost:8080/v1",  # ← ModelToll
)

response = client.chat.completions.create(
    model="gpt-4o",  # ModelToll reroutes to gpt-4o-mini automatically
    messages=[{"role": "user", "content": "Hello!"}],
)
```

### 4. Check the admin dashboard

```bash
curl -H "X-Admin-Api-Key: your-admin-key" \
     http://localhost:8080/dashboard/summary?tenant_id=default&days=30
```

---

## Features

### Scrubber Engine (layered)

| Layer | What it catches |
|-------|----------------|
| Custom regex | AWS keys, GitHub tokens, DB URLs, CNPJ, CPF, internal codes |
| Presidio NLP | Names, emails, phones, credit cards, SSNs, IPs, dates, locations |

All patterns are configurable in `config/custom_patterns.json`.

### Model Router

Automatic routing based on `config/model_routing.json`:

| Requested | Routed to | Savings |
|-----------|-----------|---------|
| `gpt-4o` | `gpt-4o-mini` | ~97% |
| `gpt-4-turbo` | `gpt-4o-mini` | ~98% |
| `claude-opus` | `claude-haiku` | ~95% |
| `gemini-1.5-pro` | `gemini-1.5-flash` | ~98% |

### Cost Arbitrage Billing

ModelToll tracks every dollar saved and takes 20% of the savings:

```
Company was spending: $500,000/month
With ModelToll:        $300,000/month
Savings:               $200,000/month
ModelToll fee (20%):    $40,000/month
Company net gain:      $160,000/month
```

### Audit Trail

Every intercepted request is logged with:
- User identity, IP, session
- Original model requested
- Scrubber findings (entity types, count)
- Routed model + provider
- Token counts
- Cost delta and savings
- Response latency + status

---

## Admin API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness probe |
| `GET /dashboard/summary` | KPI overview (costs, savings, requests) |
| `GET /dashboard/logs` | Paginated audit log with filters |
| `GET /dashboard/top-models` | Most-used source models |
| `GET /dashboard/savings` | Daily cost savings time-series |
| `GET /metrics` | Prometheus metrics |

All dashboard endpoints require `X-Admin-Api-Key` header.

---

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check src/ tests/

# Type check
mypy src/

# Run locally (dev mode)
uvicorn src.main:app --reload --port 8080
```

---

## Monetization

ModelToll's business model is **compute arbitrage**:

1. Deploy ModelToll inside an enterprise
2. Measure their current AI spend (shadow + authorized)
3. Reroute to optimized models
4. Bill 20% of the monthly savings

**This means ModelToll's revenue scales directly with the value it delivers — zero risk for the customer.**

---

## Roadmap

- [ ] Browser extension for client-side interception
- [ ] VPN mode (network-level MITM for all traffic)
- [ ] Fine-grained per-user/per-team policies
- [ ] Multi-tenant SaaS dashboard
- [ ] Slack / Teams bot integration
- [ ] Real-time cost alert webhooks
- [ ] SOC 2 Type II compliance package

---

## License

Proprietary — ModelToll © 2026
