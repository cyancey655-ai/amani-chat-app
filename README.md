# Amani Chat — AI Companion Chat Business

A real, deployable web app: hotline-style lineup of 7 AI companions, user accounts,
AI chat (OpenAI-compatible), and Stripe billing — **$1.00 per started minute**
or **$24.99/month unlimited**.

**Live demo mode:** the app boots with zero keys set. You'll see a gold
"DEMO MODE" banner — AI replies are stubbed and plan buttons activate a
*simulated* plan. **Nothing real is ever charged in demo mode.**

---

## 1. What Charity must provide (3 things)

1. **A hosting account** — Render (free tier works) or Fly.io, see below.
2. **Stripe live keys** — from the Stripe Dashboard:
   - `STRIPE_SECRET_KEY` — Developers → API keys → **Secret key** (use the *live* `sk_live_...` key for real money)
   - `STRIPE_WEBHOOK_SECRET` — created when you add the webhook endpoint (step 4 below, `whsec_...`)
   - `STRIPE_PRICE_MONTHLY` — the Price ID of the $24.99/mo recurring price (`price_...`)
   - `STRIPE_PRICE_METERED` — the Price ID of the $1.00/min metered price (`price_...`)
3. **An OpenAI API key** — `OPENAI_API_KEY` (`sk-...`). Any OpenAI-compatible
   endpoint works via `OPENAI_BASE_URL`. Add a few dollars of credit to start;
   at $1.00/minute charged to users, the API cost (fractions of a cent per
   reply) is covered many times over.

---

## 2. Stripe Dashboard setup (do this once)

1. **$24.99/mo price:** Product catalog → create product "Amani Chat Monthly" →
   Recurring, $24.99 USD, monthly → copy the **Price ID** (`price_...`) into
   `STRIPE_PRICE_MONTHLY`.
2. **Billing meter:** Billing → Meters → Create meter:
   - Event name: `amani_chat_minute` (must match `STRIPE_METER_EVENT_NAME`)
   - Display name: "Amani chat started minutes"
3. **$1.00/min metered price:** Product catalog → create product
   "Amani Chat Per Minute" → Recurring, **metered** usage, $1.00 per unit,
   select the `amani_chat_minute` meter → copy the **Price ID** into
   `STRIPE_PRICE_METERED`.
4. **Webhook:** Developers → Webhooks → Add endpoint:
   - URL: `https://YOUR-APP-URL/stripe/webhook`
   - Events: `checkout.session.completed`, `customer.subscription.updated`,
     `customer.subscription.deleted`, `invoice.payment_failed`
   - Copy the **Signing secret** (`whsec_...`) into `STRIPE_WEBHOOK_SECRET`.

**How billing works:** a user picks a plan → Stripe Checkout (subscription mode)
collects their card → the webhook activates their plan. For pay-per-minute users
the app reports **one meter event per started minute** (any minute with ≥1 user
message, idempotency-keyed so retries never double-bill); Stripe invoices the
metered subscription monthly. Subscription webhooks (`deleted`/`updated`) revoke
or pause access automatically.

---

## 3. Deploy on Render (free tier)

1. Push this folder to a GitHub repo.
2. Render Dashboard → New → **Web Service** → connect the repo.
   (Or: New → **Blueprint** and point it at `render.yaml` — env vars are pre-listed.)
3. Settings: Build command `pip install -r requirements.txt`, Start command
   `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --timeout 90`.
4. Environment tab → add every variable from `.env.example`
   (`SECRET_KEY` can be auto-generated; set `APP_BASE_URL` to your
   `https://amani-chat.onrender.com` URL; `SECURE_COOKIES=1`).
   Optional: add a Render Postgres database and set `DATABASE_URL` to its
   internal URL (otherwise a SQLite file is used — fine for starting out,
   but it resets on redeploys).
5. Deploy. Open the URL, finish the Stripe webhook step (section 2.4) with
   your real `https://...onrender.com/stripe/webhook` URL.

## 4. Deploy on Fly.io

```bash
# one-time setup
fly auth login
fly launch --no-deploy        # accepts the included fly.toml/Dockerfile

# secrets (never in code)
fly secrets set SECRET_KEY="$(openssl rand -hex 32)" \
  APP_BASE_URL="https://amani-chat.fly.dev" SECURE_COOKIES=1 \
  OPENAI_API_KEY="sk-..." OPENAI_MODEL="gpt-4o-mini" \
  STRIPE_SECRET_KEY="sk_live_..." STRIPE_WEBHOOK_SECRET="whsec_..." \
  STRIPE_PRICE_MONTHLY="price_..." STRIPE_PRICE_METERED="price_..." \
  STRIPE_METER_EVENT_NAME="amani_chat_minute"

fly deploy
```

Then add `https://amani-chat.fly.dev/stripe/webhook` in the Stripe Dashboard
(section 2.4). For a persistent database on Fly, attach Postgres
(`fly postgres create` + `fly postgres attach`) — otherwise SQLite is used.

## 5. Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in keys, or leave blank for demo mode
python wsgi.py         # http://localhost:5000
```

## 6. Environment variables (full list)

| Variable | Required | Purpose |
|---|---|---|
| `SECRET_KEY` | yes (prod) | Flask session signing — long random string |
| `APP_BASE_URL` | yes (prod) | Public URL, e.g. `https://amani-chat.onrender.com` |
| `SECURE_COOKIES` | prod | `1` on https |
| `DATABASE_URL` | no | Postgres URL; default SQLite file |
| `OPENAI_API_KEY` | for real chat | AI replies; blank = demo stub |
| `OPENAI_MODEL` | no | default `gpt-4o-mini` |
| `OPENAI_BASE_URL` | no | default `https://api.openai.com/v1` |
| `STRIPE_SECRET_KEY` | for real billing | blank = demo mode |
| `STRIPE_WEBHOOK_SECRET` | for real billing | webhook signature check |
| `STRIPE_PRICE_MONTHLY` | for real billing | `$24.99/mo` price id |
| `STRIPE_PRICE_METERED` | for real billing | `$1.00` metered price id |
| `STRIPE_METER_EVENT_NAME` | no | default `amani_chat_minute` |

## 7. Project layout

```
amani-chat-app/
  app/
    __init__.py        app factory, login manager, rate limiter
    config.py          env-only configuration
    models.py          User, Conversation, Message, MinuteUsage
    companions.py      the 7 AI personas + system prompts
    ai.py              OpenAI-compatible chat client (+ demo stub)
    stripe_service.py  Checkout sessions, meter events, webhook verify
    routes_main.py     landing, terms, privacy
    routes_auth.py     signup / login / logout
    routes_chat.py     model picker, chat room, /api/chat, history
    routes_billing.py  pricing, checkout, webhook, billing dashboard
  templates/           Jinja pages (landing, auth, chat, billing, legal)
  static/
    css/style.css      hotline-style neon theme
    js/chat.js         messaging + browser voice in/out (Web Speech API)
    img/               7 model portraits (bundled locally)
    video/             7 model intro clips (bundled locally)
  wsgi.py  requirements.txt  Procfile  render.yaml  fly.toml  Dockerfile
  .env.example  README.md
```

## 8. Safety notes

- Secrets only ever come from env vars — none are in code, logs, or the repo.
- Passwords are hashed (Werkzeug). Sessions are HTTP-only, SameSite=Lax,
  Secure in production.
- Rate limits: auth 10/min, chat API 30/min, global 600/hour.
- Stripe webhooks are signature-verified; unsigned payloads are rejected.
- 18+ age gate on the landing page + confirmation checkbox at signup.
- Demo mode is loudly bannered and can never create a real charge.
