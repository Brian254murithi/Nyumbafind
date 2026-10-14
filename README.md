# NyumbaFind — Kenyan Rental Property Platform

A professional Kenyan rental-property discovery, tenant-review, and landlord-management
platform. Built with **Django + Django REST Framework** (backend) and a hand-crafted
**HTML/CSS/vanilla JavaScript** frontend (no frameworks).

**Find a Home That Feels Right.** — Discover rentals across Kenya, compare prices,
explore tenant ratings, and make informed rental decisions.

---

## 1. Project structure

```
NyumbaFind/
├── manage.py                     # Django management script
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variable template
├── .gitignore
├── README.md                     # This file
│
├── nyumbafind/                   # Django project package
│   ├── settings.py               # Env-based settings (SQLite / PostgreSQL)
│   ├── urls.py                   # Root URL configuration
│   ├── wsgi.py / asgi.py
│
├── accounts/                     # Custom user model + auth API
│   ├── models.py                 # User with tenant/landlord/admin roles
│   ├── serializers.py / views.py / urls.py / admin.py
│   └── tests.py                  # 20 auth tests
│
├── properties/                   # Property listings
│   ├── models.py                 # Property, PropertyImage (lat/lng fields)
│   ├── geo.py                    # Pure-Python haversine + geo param validation
│   ├── serializers.py / views.py / urls.py / permissions.py
│   ├── validators.py             # Image & amenity validation
│   ├── admin.py
│   ├── tests.py                  # 43 property tests (incl. geo search)
│   └── management/commands/seed.py   # Sample data generator (geocoded)
│
├── reviews/                      # Tenant reviews & moderation
│   ├── models.py                 # Review, ReviewReport, LandlordResponse
│   ├── serializers.py / views.py / urls.py / permissions.py
│   ├── utils.py                  # Rating aggregation helpers
│   ├── admin.py
│   └── tests.py                  # 23 review tests
│
├── landlords/                    # Landlord dashboard API
│   ├── views.py / urls.py
│   └── tests.py                  # 5 dashboard tests
│
├── ai/                           # NyumbaFind AI assistant
│   ├── nlp.py                    # Intent + filter extraction
│   ├── providers.py              # Rule-based + OpenAI-compatible provider
│   ├── views.py / urls.py
│   └── tests.py                  # 22 AI tests
│
├── payments/                     # M-Pesa Daraja integration
│   ├── models.py                 # PaymentTransaction, PaymentStatusLog,
│   │                             #   PaymentConfiguration (admin-editable)
│   ├── mpesa_service.py          # Reusable Daraja service (OAuth, STK Push,
│   │                             #   TransactionStatusQuery, callback validation)
│   ├── serializers.py / views.py / urls.py / permissions.py / admin.py
│   ├── tests.py                  # 46 payment tests (Daraja mocked)
│   └── management/commands/reconcile_payments.py
│
└── frontend/                     # Vanilla JS frontend (served by Django)
    ├── index.html                # Single-page app shell + M-Pesa payment modal
    ├── style.css                 # Design system
    └── script.js                 # Application logic
```

---

## 2. Windows PowerShell installation

Prerequisites: **Python 3.10+** and **pip**.

```powershell
# 1. Enter the project folder
cd "D:\Antygravity Projects\NyumbaFind"

# 2. (Recommended) create a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create a local environment file (optional for dev)
copy .env.example .env

# 5. Apply database migrations
python manage.py migrate

# 6. (Optional) Load realistic sample listings, tenants and reviews
python manage.py seed

# 7. Create an admin account for moderation
python manage.py createsuperuser

# 8. Start the development server
python manage.py runserver
```

Open **http://127.0.0.1:8000** in your browser.

To reset sample data: `python manage.py seed --reset`

---

## 3. Environment variables

Copy `.env.example` to `.env` and adjust. All secrets stay server-side.

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | dev placeholder | Cryptographic signing (change in production) |
| `DJANGO_DEBUG` | `True` | Debug mode (set `False` in production) |
| `DJANGO_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Comma-separated allowed hosts |
| `DATABASE_URL` | *(empty = SQLite)* | PostgreSQL URL, e.g. `postgres://user:pass@127.0.0.1:5432/nyumbafind` |
| `CORS_ALLOWED_ORIGINS` | `http://127.0.0.1:8000,...` | Origins allowed to call the API cross-origin |
| `AI_PROVIDER` | `rule_based` | `rule_based` or `openai` |
| `OPENAI_API_KEY` | *(empty)* | API key for the OpenAI-compatible provider |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Any OpenAI-compatible endpoint |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model name |
| `AI_RATE_LIMIT` | `10/min` | Chat endpoint throttle |
| `DJANGO_SECURE` | *(empty)* | Set `true` to enable HSTS/SSL-redirect/cookie flags |
| `MPESA_ENVIRONMENT` | `sandbox` | `sandbox` or `production` |
| `MPESA_CONSUMER_KEY` | *(empty)* | Daraja app consumer key |
| `MPESA_CONSUMER_SECRET` | *(empty)* | Daraja app consumer secret |
| `MPESA_SHORTCODE` | *(empty)* | Paybill shortcode (or 174379 in sandbox) |
| `MPESA_PASSKEY` | *(empty)* | Daraja passkey (sandbox default: `bfb279f9aa9bdb412d1a3f9a...` for shortcode 174379) |
| `MPESA_CALLBACK_URL` | *(empty)* | Public HTTPS callback, e.g. `https://example.com/api/payments/callback/` |
| `MPESA_INITIATOR` | *(empty)* | Optional: registered initiator for TransactionStatusQuery (reconciliation) |
| `MPESA_SECURITY_CREDENTIAL` | *(empty)* | Optional: initiator security credential from the Daraja portal |

**PostgreSQL (production):** set `DATABASE_URL` and install
`psycopg2-binary`. SQLite is used automatically when `DATABASE_URL` is empty.

---

## 4. API endpoint documentation

Base URL: `http://127.0.0.1:8000/api`. Authentication uses DRF token auth —
send the header `Authorization: Token <token>` for protected endpoints.

### Authentication
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register/` | Register tenant or landlord. Returns `{token, user}`. |
| `POST` | `/api/auth/login/` | Login with username **or** email. Returns `{token, user}`. |
| `POST` | `/api/auth/logout/` | Invalidate the current token (auth required). |
| `GET` | `/api/auth/me/` | Current user profile (auth required). |
| `PATCH` | `/api/auth/me/` | Update own settings — landlords may set `{"accepts_payments": true}` to authorize rent collection (auth required). |

### Properties
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/properties/` | List & filter. Params: `county`, `town`, `estate`, `property_type`, `min_rent`, `max_rent`, `bedrooms`, `available`, `featured`, `q`, `sort` (`newest`,`price_asc`,`price_desc`,`rating`), `page`, `page_size`. **Geo:** `latitude`+`longitude`+`radius` (km, default 10, max 200) for distance search; `min_lat`, `max_lat`, `min_lng`, `max_lng` for bounding-box search; `has_coords=true` for listings with coordinates only. All coordinates are validated server-side (−90…90 / −180…180). |
| `POST` | `/api/properties/` | Create a listing (landlord/admin only, multipart for images). |
| `GET` | `/api/properties/{id}/` | Public property detail incl. rating summary + gallery. |
| `PATCH` / `PUT` | `/api/properties/{id}/` | Update (owner or admin only). |
| `DELETE` | `/api/properties/{id}/` | Delete (owner or admin only). |
| `POST` | `/api/properties/{id}/images/` | Upload extra photos (owner/admin only, max 12 total). |

### Locations
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/locations/search/` | Location autocomplete. `?q=` (min 2 chars) matches real counties, towns and estates from the database with listing counts and representative coordinates (property centroid, or a known county centroid). `?all=1` lists every county with listings. |

### Reviews
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/properties/{id}/reviews/` | Approved reviews + rating summary (avg, distribution, category averages). |
| `POST` | `/api/properties/{id}/reviews/` | Submit a review (authenticated tenant, once per property, 7 ratings 1–5). |
| `GET` | `/api/reviews/{id}/` | Single review detail. |
| `PATCH` | `/api/reviews/{id}/` | Owner edits own review; admins set `status`/`is_verified`. |
| `DELETE` | `/api/reviews/{id}/` | Owner or admin. |
| `POST` | `/api/reviews/{id}/report/` | Report a review (reason + description). Moves it to moderation. |
| `POST` | `/api/reviews/{id}/response/` | Landlord who owns the property responds publicly. |
| `GET` | `/api/reviews/top/` | Recent approved reviews platform-wide. |
| `GET` | `/api/reviews/summary/` | Platform-wide rating summary. |

### Landlord
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/landlord/dashboard/` | Portfolio stats, listings with ratings, recent reviews (landlord/admin). |

### AI assistant
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/ai/chat/` | Body `{"message": "..."}`. Returns `{reply, intent, provider, filters_applied, properties}`. Rate-limited (default 10/min). |

**Error format:** `{"errors": {"field": ["message"]}}` with appropriate HTTP status
(400 validation, 401 auth required, 403 forbidden, 404 not found, 429 throttled).

### Payments (M-Pesa Daraja)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/payments/config/` | Public: enabled payment purposes + fee amounts (no secrets). |
| `POST` | `/api/payments/stk-push/` | Initiate an STK Push. Body `{purpose, amount, phone_number, property_id?, description?}`. Creates a **processing** transaction — never successful until the callback confirms. |
| `GET` | `/api/payments/{reference}/status/` | Transaction status + M-Pesa receipt (owner or admin). |
| `GET` | `/api/payments/history/` | Caller's transactions (all, for admins). Filters: `purpose`, `status`. |
| `POST` | `/api/payments/callback/` | Safaricom STK Push callback — server-to-server, correlated by `CheckoutRequestID`, idempotent. |
| `POST` | `/api/payments/reconcile/` | Admin: expire or re-query payments stuck in processing. |

**Payment purposes** (enabled by the administrator in Django admin →
*Payment configuration*): `listing_fee` (landlords), `viewing_fee`
(tenants booking a viewing), `rental_payment` (tenants, only when the
landlord has set `accepts_payments=true`). Amounts must match the
configured fee / property rent. Valid KSh range: 1–150,000 per
transaction.

**Security model:** only the Safaricom callback (or an admin via
reconciliation) can mark a payment successful — never a browser
request. Callbacks are correlated by the unique `CheckoutRequestID`,
validated against the expected amount, and processed idempotently
(duplicate callbacks are acknowledged without re-applying). Daraja
does not provide a callback signature that can be independently
verified, so production deployments should additionally restrict
`/api/payments/callback/` to Safaricom's published IP ranges at the
infrastructure level.

**Frontend caching:** the SPA shell (`/`) is served with
`Cache-Control: no-store` so browsers never run a stale copy of
`index.html` (e.g. after an upgrade that changes asset URLs).
Static assets keep normal caching.

---

## 5. AI provider configuration

The assistant works out of the box with the **built-in rule-based engine**
(`AI_PROVIDER=rule_based`). It extracts budget, county/estate, property type and
bedroom count from natural language, queries the real database, and never invents
listings, prices or ratings. It clearly identifies itself as a limited assistant.

To connect a language model, set in `.env`:

```powershell
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1   # or any OpenAI-compatible endpoint
OPENAI_MODEL=gpt-4o-mini
```

The key is read **server-side only** and never exposed to the browser. If the AI
service is unreachable, the assistant automatically falls back to the rule-based
engine and says so. To swap providers, add a class implementing
`generate_reply(message, filters, properties, intent)` in `ai/providers.py` and
return it from `get_provider()`.

---

## 6. Geographic search

Listings carry optional `latitude` / `longitude` coordinates
(`DecimalField(9, 6)`, nullable). The properties API supports
distance and bounding-box search on top of them:

- `latitude` + `longitude` + `radius` (km, default 10, max 200) —
  distance search
- `min_lat` / `max_lat` / `min_lng` / `max_lng` — bounding-box search
- `has_coords=true` — only listings with coordinates

All coordinates are validated server-side (−90…90 / −180…180).

### Data model
`Property.latitude` / `Property.longitude` (`DecimalField(9, 6)`,
nullable). Listings without coordinates still appear in the normal
list view. The seed command (`python manage.py seed`) geocodes all
14 sample listings across Nairobi, Kiambu, Mombasa and Nakuru, and
backfills coordinates when re-run against an older database.

### How the geography works
No PostGIS dependency — `properties/geo.py` implements a pure-Python
haversine and a bounding-box pre-filter that runs in SQL, so the same
code works on SQLite (dev) and PostgreSQL (production). Distance search
uses a generous SQL bounding box, then refines precisely in Python.

County centroids (public geographic facts) are used as representative
coordinates when a county has no geocoded listings yet; property data
itself always comes from the database.

---

## 7. M-Pesa (Daraja) payment integration

NyumbaFind integrates Safaricom's official **M-Pesa Daraja API**
for STK Push payments. The reusable service lives in
`payments/mpesa_service.py`; Django views only orchestrate.

### Supported payment types
| Purpose | Who pays | Amount |
|---|---|---|
| `listing_fee` | Landlord | Admin-configured (default KSh 1,000) |
| `viewing_fee` | Tenant booking a viewing | Admin-configured (default KSh 500) |
| `rental_payment` | Tenant | The property's monthly rent — only when the landlord has set *"Collect rent via NyumbaFind"* |

The administrator enables purposes in **Django admin → Payment
configuration**. Nothing is ever charged without the user
confirming the M-Pesa prompt on their own phone.

### Payment flow
1. Signed-in user picks a payment (property page or dashboard).
2. Backend validates purpose, amount, phone and ownership.
3. Frontend shows the amount + phone field and asks for confirmation.
4. Backend creates a **pending** transaction and calls Daraja.
5. User approves privately on their phone (M-Pesa PIN on their device —
   NyumbaFind never sees or stores the PIN).
6. Safaricom POSTs the result to `MPESA_CALLBACK_URL`.
7. Django validates the callback, matches the `CheckoutRequestID`,
   checks the amount, and records the outcome **idempotently**.
8. Frontend polls `GET /api/payments/{reference}/status/` and shows
   the receipt only after server-side confirmation.

### STK Push workflow notes
- A accepted push is **processing**, not success. Only the callback
  (or admin reconciliation) confirms success.
- Result codes: `0` success · `1032` cancelled · `1037` timeout
  (expired) · anything else → failed with a sanitized message.
- Duplicate callbacks and replayed callbacks are acknowledged
  without re-applying the outcome (guarded by a row lock +
  terminal-state check).
- A browser request alone can never mark a payment successful.

### Sandbox setup (Windows PowerShell)

```powershell
# 1. Register an app at https://developer.safaricom.co.ke
#    (Daraja portal → My Apps → "Register App"). Copy the
#    Consumer Key and Consumer Secret.

# 2. Configure .env (sandbox is the default)
$envFile = ".env"
@'
MPESA_ENVIRONMENT=sandbox
MPESA_CONSUMER_KEY=your_consumer_key
MPESA_CONSUMER_SECRET=your_consumer_secret
MPESA_SHORTCODE=174379
MPESA_PASSKEY=bfb279f9aa9bdb412d1a3f9a0d8a5f6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e
MPESA_CALLBACK_URL=https://your-ngrok-url.ngrok-free.app/api/payments/callback/
'@ | Set-Content $envFile -Encoding utf8   # merge into your existing .env

# 3. Apply migrations and start the server
python manage.py migrate
python manage.py runserver 127.0.0.1:8000

# 4. Expose a PUBLIC HTTPS callback endpoint.
#    Safaricom cannot reach localhost — use a tunnel:
winget install ngrok.ngrok
ngrok http 8000
#    Copy the https://*.ngrok-free.app URL into MPESA_CALLBACK_URL
#    (must be the /api/payments/callback/ path).

# 5. Test with a sandbox phone: register a test number at
#    https://sandbox.safaricom.co.ke (shortcode 174379,
#    passkey bfb279f9aa9bdb412d1a3f9a0d8a5f6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e),
#    then enable a payment purpose in the Django admin and pay
#    from the property page. Approve the prompt on the sandbox phone.
```

### Switching to production
1. Complete Safaricom's onboarding (business verification, Paybill
   or till number registration).
2. Set `MPESA_ENVIRONMENT=production` and replace all credentials
   with the live ones, and `MPESA_CALLBACK_URL` with your HTTPS URL.
3. Optional (for the reconciliation endpoint): register a Daraja
   initiator and set `MPESA_INITIATOR` /
   `MPESA_SECURITY_CREDENTIAL`.
4. Restrict `/api/payments/callback/` to Safaricom's published
   callback IP ranges at the infrastructure (firewall/CDN) level —
   Daraja callbacks do not carry an independently verifiable
   signature, so the endpoint relies on CheckoutRequestID
   correlation, amount validation and idempotent processing.

### Reconciliation
Payments stuck in *processing* (e.g. callback never arrived) are
handled by `POST /api/payments/reconcile/` (admin) or
`python manage.py reconcile_payments`. With an initiator
configured this queries Daraja's TransactionStatus API; otherwise
it expires payments older than `payment_validity_minutes`
(default 15).

### Test coverage
`payments/tests.py` (46 tests, all mocked — no network, no real
money) covers phone validation, amount validation, authorization
rules, STK Push failures, timeouts, missing credentials, every
callback outcome, duplicate/replayed callbacks, amount mismatches,
unknown checkout IDs, duplicate-payment prevention, status
permissions, and reconciliation.

---

## 8. Frontend ↔ backend connection

The frontend is served by Django itself at `/`, so API calls are same-origin by
default (`API_BASE = ""`). To point the frontend at another origin, define this
**before** loading `script.js`:

```html
<script>
  window.NYUMBAFIND_API_BASE = "https://api.example.com/api";
</script>
<script src="/static/script.js"></script>
```

No API keys or credentials are stored in `script.js` — auth tokens live in
`localStorage` and are sent via the `Authorization` header.

---

## 9. Running the tests

```powershell
python manage.py test
```

**Result: 159 tests, all passing** (accounts 20, properties 43,
reviews 23, landlords 5, AI 22, payments 46). The suite uses a
fast password hasher during tests only.

Coverage includes: registration/login, role enforcement, property
CRUD and ownership, filtering/search/sorting, image validation,
**geographic search (radius, bounding box, coordinate validation,
has-coords filter, location autocomplete)**, review submission with
rating validation, duplicate-review prevention, landlord response
permissions, review reporting, admin-only verification, dashboard
stats, AI intent parsing, search flow, the missing-provider
fallback, and the full M-Pesa payment lifecycle (validation,
authorization, STK Push errors, callback outcomes, idempotency,
permissions, reconciliation).

---

## 10. Django administration

Sign in at **http://127.0.0.1:8000/admin** (superuser via `createsuperuser`).
Configured for: Users, Properties, Property Images, Reviews, Review Reports,
Landlord Responses and **Payments** (transactions, status logs, and the
singleton *Payment configuration* where payment purposes and fee amounts
are enabled) — with search, filters, ordering, autocomplete and inline
moderation controls (review status and verification are editable directly in the
review list).

---

## 11. Deployment guidance

1. Set `DJANGO_DEBUG=False`, a strong `DJANGO_SECRET_KEY`, and real
   `DJANGO_ALLOWED_HOSTS`.
2. Use PostgreSQL via `DATABASE_URL`; run `python manage.py migrate`.
3. Collect static files: `python manage.py collectstatic --noinput` and serve
   `STATIC_ROOT` (`staticfiles/`) plus `MEDIA_ROOT` (`media/`) from your web
   server or CDN.
4. Put the app behind Gunicorn/uWSGI + Nginx; enable `DJANGO_SECURE=true` for
   HSTS, SSL redirect and secure cookies.
5. Restrict `CORS_ALLOWED_ORIGINS` to your frontend origin if serving the
   frontend separately.
6. Configure a real email backend for production notifications.
7. Set `AI_PROVIDER`/`OPENAI_API_KEY` if you want LLM-powered answers.
8. **Payments:** the app must be reachable over public HTTPS for the
   M-Pesa callback (`MPESA_CALLBACK_URL`). Verify sandbox transactions
   end-to-end before switching `MPESA_ENVIRONMENT=production`.

---

## 12. Known limitations

- **Sample listings:** seeded data is flagged `is_sample=true` and labelled
  "Sample" in the UI; photos are licensed Unsplash stock images used as
  placeholders.
- **Payments:** M-Pesa integration follows Daraja's official STK Push flow
  with sandbox support. Live payments require valid Daraja credentials, a
  registered Paybill/shortcode, a publicly reachable HTTPS callback endpoint,
  and a successful sandbox test transaction before production use. Daraja
  callbacks carry no independently verifiable signature — correlation relies
  on the unique `CheckoutRequestID`, server-side amount validation and
  idempotent processing; restrict the callback URL to Safaricom IP ranges
  at the infrastructure level in production.
- **Image hosting:** uploaded photos are stored on the local filesystem
  (`media/`); configure S3/Cloud storage for multi-server deployments.
- **Rule-based AI:** without an API key the assistant handles structured rental
  queries well but is not a general conversationalist.
- **Email/phone verification:** fields exist but the verification workflow
  (email sending) requires an SMTP configuration.

---

*Built with Django, Django REST Framework, and vanilla JavaScript.
KSh pricing throughout. Sample data for demonstration only.*
