# CommPal Payments API

An extensible Django REST foundation for payment checkout lifecycle management. The payment app is intentionally isolated so customer identity, carts/orders, subscriptions, refunds, and production provider adapters can be introduced independently.

## Requirements

- Python **3.14.7**
- Django 6.0 (supports Python 3.14)

## Setup

Create and activate an environment using Python 3.14.7, install the project and development extras, then migrate the database:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, and `DJANGO_ALLOWED_HOSTS` through environment variables. Set `DATABASE_URL` for a production database; SQLite is used by default for local development. Never deploy with the development secret or DEBUG enabled.

## API

All payment endpoints require an authenticated Django user except provider webhooks. Authentication defaults to DRF session and basic authentication; replace these with the host application's chosen authentication before public deployment.

- `POST /api/payments/` — create a checkout intent. JSON: `amount` (positive decimal), `currency` (3 uppercase letters), optional `description`. Optional `Idempotency-Key` header makes retries safe for each user.
- `GET /api/payments/` — list only the authenticated user's payments.
- `GET /api/payments/{uuid}/` — retrieve one owned payment.
- `POST /api/payments/{uuid}/cancel/` — cancel a pending payment.
- `POST /api/payments/webhooks/` — receive verified provider events.

Webhook bodies use normalized event JSON with `id`, `type` (`payment.succeeded` or `payment.failed`), and `payment_id`. Signature is HMAC-SHA256 in `X-Payment-Signature` (hex digest, optionally prefixed `sha256=`). Configure `PAYMENTS_WEBHOOK_SECRET` and `PAYMENTS_WEBHOOK_PROVIDER` for the integration. Provider-specific verification, normalization, retries, monitoring, and secret rotation should be implemented in the provider integration before production.

## Extending providers

Implement the `PaymentProvider` protocol in `payments/providers/base.py` and provide a provider class with `name` and `create_checkout(payment)`. Set `PAYMENTS_PROVIDER` to its dotted import path. Production providers should create hosted checkout sessions, keep card data entirely in compliant provider-hosted forms/SDKs, and normalize and verify callbacks before calling the domain event service. Do not store PAN, CVC, or other raw card credentials in this application.

The local development adapter creates only a reference; it does not charge, collect card information, or mark a payment successful. Do not use it to process real money.

## Tests

```powershell
python manage.py test
```
