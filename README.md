# BisaRx - Clinical AI Pharmacist

BisaRx is an AI-powered healthcare assistant designed for the Ghanaian context. It acts as a bridge between patients and licensed pharmacists, gathering symptoms, checking against clinical guidelines, and providing a patient summary for professional review.

## Tech Stack

- **Backend**: FastAPI (Python 3.10+)
- **Database**: SQLite with SQLAlchemy
- **AI Engine**: OpenAI/DeepSeek API (RAG with PDF guidelines)
- **Frontend**: Vanilla HTML/CSS/JS (Modern 'Rich' Design)
- **Auth**: JWT + OAuth2 (Google)

## Prompt Engineering & Challenge Alignment

### Chosen Vertical

**PromptWars – AI Prompt Challenge**. The application domain is pharmacy symptom
intake for patients in Ghana. This submission follows the documentation and size
requirements supplied for evaluation; it does not claim organizer certification.

BisaRx applies the **PromptWars – AI Prompt Challenge** theme to a concrete
task: turning a patient's symptom conversation into an intake report for a
licensed pharmacist. The prompt pipeline is implemented in `chat_engine.py`;
this documents the application, rather than claiming official challenge rules
or a clinical accuracy score.

### Approach and Logic

Separate conversational intake, local evidence retrieval, and professional
decision-making. A focused prompt gathers missing history one question at a
time; retrieved material supplies context; a structured report supports the
pharmacist's assessment. Local fallback helpers keep intake available during
model failures. Language lookup preserves unmatched text rather than inventing
a translation. The implementation details and limits are:

- **System instructions:** `SYSTEM_PROMPT` defines the assistant's clinical
  intake role, concise tone, language matching, emergency escalation, and
  treatment boundaries. `build_system_messages()` puts these instructions
  before the conversation for streaming; `process_chat()` handles standard chat.
- **Guided symptom intake:** prompts ask one focused question at a time, following
  site, onset/duration, character, severity/progression, associated symptoms,
  aggravating/relieving factors, and relevant medical history. `[CONSULT_READY]`
  signals handoff after sufficient information; local fallback helpers support
  intake when the model is unavailable. Body-map selections draft patient text.
- **Twi handling:** `translate_twi_to_english()` normalizes and matches whole
  phrases against the local bilingual CSV. A match supplies English text for
  retrieval and adds Twi response instructions; unmatched text is preserved.
  This limited lookup is not a general-purpose language detector. An optional
  Abena translation helper also exists, but is not used by this prompt builder.
- **Retrieval grounding (RAG):** local PDF text is split into overlapping word
  chunks. `get_relevant_pdf_context()` ranks chunks by token overlap with patient
  messages and adds relevant excerpts with page numbers to the system context.
  A bounded base excerpt is also included. Configure `GUIDELINES_PDF_PATH` for
  the intended clinical source; the default selects the first local PDF. Source
  suitability, currency, and model faithfulness require human evaluation.
- **Structured patient summary:** `SUMMARY_PROMPT` requests a `SUMMARY:` line
  followed by chief complaint, HPI, associated symptoms/relevant negatives,
  red flags/urgency, patient context, and pharmacist guidance. The resulting
  report is model-generated Markdown, not a schema-validated diagnosis.
- **Non-prescribing and review guardrails:** the patient-facing system prompt
  explicitly prohibits prescribing or recommending specific drug names, directs
  danger signs to urgent hospital care, and assigns diagnosis/treatment decisions
  to a licensed pharmacist. AI reports and pharmacist-facing suggestions remain
  decision support. Ordering requires a reviewed case. Prompt instructions and
  deterministic tests do not prove medical safety or prevent every unsafe output.

### How the Solution Works

1. A patient types symptoms or uses the body map to draft a message. An optional
   image can supply conservative visual observations when Gemini is configured.
2. The frontend sends conversation history to `/api/chat` or `/api/chat/stream`.
   The backend performs local Twi phrase lookup and retrieves matching PDF chunks.
3. System instructions, retrieved context, and history guide the model's next
   intake question. When enough information is available, the handoff marker and
   intake logic create a case for pharmacist review.
4. The application prepares a structured patient summary. A licensed pharmacist
   must review the case and make diagnosis, treatment, referral, and medication
   decisions; AI output alone is not authorization to treat.
5. Patients receive review updates through the existing API/WebSocket flows.
   Ordering requires a reviewed case; configured Moolre services support payment
   initialization and SMS. Offline tests substitute deterministic service mocks.

### Assumptions Made

- **Clinical non-prescribing:** BisaRx is an intake and decision-support tool.
  Its patient-facing AI must not prescribe or select specific medication.
- **Mandatory pharmacist review:** every AI case summary requires licensed
  pharmacist review before clinical action. Staff access and actual review
  quality remain operational responsibilities; prompts do not guarantee safety.
- Patients provide an accurate symptom history. Missing or uncertain information
  must be clarified by the reviewer; urgent symptoms require hospital care rather
  than waiting for routine pharmacy review.
- Operators supply appropriate, current clinical guidelines and have permission
  to use the bundled/reference data. The presence of a PDF is not evidence of its
  clinical completeness or currency.
- Local Twi coverage is limited to CSV phrase matches. Unmatched text and model
  translations require clarification or human review when meaning is uncertain.
- Live model, image, SMS, and payment capabilities require operator-provided
  environment configuration and connectivity. Offline tests validate software
  behavior, not clinical accuracy, translation quality, or live service delivery.
- The **10 MB submission budget** is interpreted as source/assets excluding
  `.git`, dependencies, caches, local databases, secrets, and generated previews.
  If organizers count Git history, this existing repository does not meet that
  interpretation; see the repository-size note below.

### Offline evaluation tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The pytest suite includes the existing smoke tests plus real HTTP route tests,
isolated in-memory SQLite fixtures, prompt construction, language lookup, intake
helpers, and guest contact/order success and rejection paths. Model evidence,
SMS, and payment responses use fixtures/mocks; external HTTP transports are
blocked. Tests ignore local `.env` credentials and do not run production startup
migrations or seeds. No live LLM or Moolre keys are needed. These are software
contract tests, not a clinical evaluation or a live payment integration test.

## 1) Install Dependencies

Ensure you have Python 3.10 or higher installed.

```bash
pip install -r requirements.txt
```

## 2) Configure Environment

Edit `.env` and set your keys:

- `DEEPSEEK_API_KEY`: Your model API key.
- `SECRET_KEY`: A long random string for JWT security.
- `ADMIN_ACCESS_CODE`: Shared credential for the `/admin` portal. If unset,
  `ADMIN_PASSWORD` is accepted instead. Either setting provisions the admin
  account; `ADMIN_USERNAME` and `ADMIN_EMAIL` optionally customize its identity.
  When both credentials are set, the portal requires `ADMIN_ACCESS_CODE`.
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`: For Google Auth integration.
- `APP_PORT`: Local server port (default `8000`). Change this if `8000` is already in use.
- `LLM_TIMEOUT_SECONDS`: Timeout for model API calls (default `45`).
- `LLM_MAX_RETRIES`: Number of automatic retries for transient API failures (default `2`).
- `VERIFY_SSL`: Keep `true` for normal use. For local SSL troubleshooting only, set `false`.
- `MOOLRE_BASE_URL`: MOOLRE API base URL (default `https://api.moolre.com`).
- `MOOLRE_API_USER`: API username header value (`X-API-USER`) for payments.
- `MOOLRE_API_PUBKEY`: Public key header value (`X-API-PUBKEY`) for payment link initialization.
- `MOOLRE_API_VASKEY`: VAS key header value (`X-API-VASKEY`) for SMS sending.
- `MOOLRE_ACCOUNT_NUMBER`: Merchant account number used to create payment links.
- `MOOLRE_SMS_SENDER_ID`: Sender ID registered on your MOOLRE account.
- `MOOLRE_SMS_PATH`: SMS endpoint path (default `/open/sms/send`).
- `MOOLRE_PAYMENT_PATH`: Payment-link endpoint path (default `/embed/link`).
- `MOOLRE_PAYMENT_CALLBACK_URL`: Public backend webhook URL for MOOLRE callbacks.
- `MOOLRE_PAYMENT_REDIRECT_URL`: Frontend URL to return to after checkout.
- `MOOLRE_TIMEOUT_SECONDS`: Timeout for MOOLRE API calls (default `20`).

## 3) Run the Application

Start the FastAPI server using Uvicorn:

```bash
python -m uvicorn main:app --port 8000 --reload
```

Or run the script directly (reads `APP_HOST`/`APP_PORT` from `.env`):

```bash
python main.py
```

Open: [http://localhost:8000](http://localhost:8000)

## Features

- **Clinical AI Chat**: Guided dialogue for symptom gathering.
- **Twi Language Support**: Local bilingual phrase lookup with Twi response instructions when a match is found.
- **RAG Implementation**: Local PDF excerpts provide context for AI intake; operators must verify the configured source's clinical suitability.
- **Pharmacist Dashboard**: Licensed professionals can review pending cases.
- **Body Map**: Interactive visual tool for selecting symptom areas.

## Frontend + Backend Hosting Alignment

- The frontend is configured to call same-origin API routes by default (`/api` and `/ws`).
- `vercel.json` rewrites proxy those requests to the live backend (`https://bisarx-8ym0.onrender.com`), so frontend and backend work together from one public frontend domain without exposing backend hostnames in client code.

## Guest SMS + Payment Integration

### International email sign-in and notifications

Patients outside Ghana choose **Email** in the patient sign-in form. Email is
sent through Gmail API over HTTPS; no custom domain or SMTP connection is needed.
Use a dedicated Gmail account. Configure these secrets directly in Render:
`GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, and
`GMAIL_SENDER` (the authorized Gmail address). Save and redeploy. Do not paste
tokens or client secrets into chat or commit them. Old Resend variables are unused.

Google setup:

1. Create/select a Google Cloud project and enable **Gmail API**.
2. Configure Google Auth Platform branding and audience. During testing, add
   the sending Gmail account as a test user. Testing refresh tokens for Gmail
   scopes expire after seven days; complete the appropriate production setup
   before relying on unattended delivery.
3. Create a Web application OAuth client. Add
   `https://developers.google.com/oauthplayground` as an authorized redirect URI.
4. Open Google OAuth Playground, enable **Use your own OAuth credentials** in
   settings, and enter that client's ID and secret there. Request only
   `https://www.googleapis.com/auth/gmail.send` and authorize the dedicated Gmail
   account. Request offline access and exchange the authorization code for tokens.
5. Copy the refresh token directly into Render as `GMAIL_REFRESH_TOKEN`; copy
   the client ID/secret into the matching variables. Set `GMAIL_SENDER` to the
   exact authorized account. A short-lived access token is not a refresh token.

The app refreshes authorization server-side before sending each message. If
authorization is revoked or expires, email requests fail visibly and need
reauthorization. No automatic send retry is performed after an ambiguous failure.
Gmail sending limits apply. A live inbox test is still required after setup.
See https://developers.google.com/workspace/gmail/api/guides/sending and
https://developers.google.com/identity/protocols/oauth2/web-server.

Email OTP uses `/api/auth/email/otp/request` and `/api/auth/email/otp/verify`.
Codes expire in five minutes, are single-use, permit five incorrect attempts,
and allow at most three requests per destination in ten minutes. Email
and SMS challenges are separate. Existing patient emails reuse their patient
account; admin accounts must use the admin portal. Choosing a different email
from an existing phone-only account creates a separate account, not a merge.

Patients without a Ghana phone number receive feedback by email and in their
portal. Available, verified pharmacists without a Ghana phone number receive
new-case alerts at the email saved by the admin. Ghana numbers continue using
Moolre. Guests must sign in by email for email feedback. Provider acceptance
does not guarantee inbox delivery. The admin-only endpoint
`/api/admin/integrations/email` reports configuration presence without secrets.

### Ghana SMS configuration

In the Render service serving `bisarx-8ym0.onrender.com`, configure:

- `MOOLRE_API_VASKEY`: the key from the Moolre **SMS service**, not a payment key.
- `MOOLRE_SMS_SENDER_ID`: the exact registered, approved sender ID (maximum 11 characters).
- `MOOLRE_BASE_URL=https://api.moolre.com`
- `MOOLRE_SMS_PATH=/open/sms/send`
- `APP_ENV=production`
- `FRONTEND_URL`: the public patient portal origin used in SMS links.

Save and redeploy after changing variables. Entries marked `sync: false` in
`render.yaml` declare required operator input; their presence in that file does
not confirm that values exist in the live service. Moolre also requires an SMS
bundle and sender approval.

An authenticated admin can inspect `/api/admin/integrations/sms` for missing
runtime variable names and the count of verified, available pharmacists with
phone numbers. The endpoint never returns keys. Configuration presence does
not prove sender approval, SMS balance, or handset delivery.

Patients request a six-digit code through `/api/auth/otp/request` and verify it
through `/api/auth/otp/verify`. Codes expire after five minutes. Production
never returns the code in the response if SMS fails.

New cases alert verified pharmacists who are accepting cases and have a phone
number, in addition to dashboard updates. Pharmacist feedback is saved to the
patient's portal, broadcast over its live connection, and sent by SMS even if
the patient is online. A failed SMS does not discard the portal feedback.
Long feedback may consume multiple SMS segments.

- Guests can now submit a phone number after AI intake using:
  - `POST /api/cases/{case_id}/guest-contact`
- When pharmacists complete a guest review, the backend can send SMS updates via MOOLRE.
- When a patient orders a reviewed prescription, the backend attempts MOOLRE payment initialization and returns payment checkout information in the order response.

## Security & Ethics

- BisaRx does NOT prescribe medication directly.
- All AI summaries MUST be reviewed by a human pharmacist.
- Passwords use bcrypt hashing and authentication uses JWT. These controls do not encrypt all patient data; deployment operators must configure appropriate storage and transport protection.

## Repository Hygiene & Submission Size

The size audit on 2026-11-25 found approximately **7.1 MB of submission files**
(decimal MB, including the evaluation changes), below a conservative
**10,000,000-byte** source budget. Large files retained because the application
loads them at runtime:

| File | Bytes | Purpose |
|---|---:|---|
| `medicine_dataset.csv` | 3,946,827 | Local medicine lookup and pharmacist context |
| `Public%20-%20Twi%5BTwi-En%5D_70.csv` | 1,015,957 | Local bilingual phrase lookup |

An unused, byte-identical root logo copy was removed. `static/logo.png` and
`static/pwa-icon.png` retain their existing, referenced URLs. Generated browser
artifacts, pytest caches, dependencies, environment files, and local databases
are excluded by `.gitignore`; do not include them in an evaluation upload.

**History caveat:** the existing `.git` directory is about **25.60 MB** (the packed
objects alone are about **24.35 MiB**). A full clone is therefore above 10 MB even
though the submission files are below it. Removing a current file does not remove
its historical blobs. Submit a source-only archive if permitted by the organizers;
if the limit includes history, obtain agreement on a submission method before
claiming compliance. This pass does not rewrite or force-push existing history.

All evaluation changes remain on the existing `main` branch. No extra working
branch, generated dependency tree, or deployment configuration change is needed.

## Run with Docker Compose

Docker Desktop must be running with Linux containers. From this directory:

```powershell
Copy-Item .env.docker.example .env.docker
# Edit .env.docker: set a long random SECRET_KEY and your provider credentials.
docker compose up --build -d
```

Open http://localhost:8000 (patient), http://localhost:8000/pharmacist,
or http://localhost:8000/admin. The API and frontend share the same origin;
WebSockets connect directly to the app. Sign in before chatting, using Ghana
SMS or international email verification. Configure the corresponding Moolre
or Gmail credentials to deliver real codes. Set ADMIN_ACCESS_CODE for admin access.
The ignored .env.docker stays on the host and is never copied into the image.

```powershell
docker compose ps
docker compose logs --tail 100 app
docker compose down
```

The bisarx-data named volume preserves the SQLite database across container
rebuilds and `down`. Do not add `--volumes` unless you intend to erase local data.
This setup binds only to localhost and uses one process for WebSocket delivery.
It does not copy or migrate the hosted production database. To host elsewhere,
override FRONTEND_URL, GOOGLE_REDIRECT_URI and CORS_ORIGINS and configure HTTPS.
