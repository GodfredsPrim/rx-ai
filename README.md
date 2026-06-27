# BisaRx (RxAI Ghana) - Clinical AI Pharmacist

BisaRx is an AI-powered healthcare assistant designed for the Ghanaian context. It acts as a bridge between patients and licensed pharmacists, gathering symptoms, checking against clinical guidelines, and providing a patient summary for professional review.

## Tech Stack

- **Backend**: FastAPI (Python 3.10+)
- **Database**: SQLite with SQLAlchemy
- **AI Engine**: OpenAI/DeepSeek API (RAG with PDF guidelines)
- **Frontend**: Vanilla HTML/CSS/JS (Modern 'Rich' Design)
- **Auth**: JWT + OAuth2 (Google)

## 1) Install Dependencies

Ensure you have Python 3.10 or higher installed.

```bash
pip install -r requirements.txt
```

## 2) Configure Environment

Copy `.env.example` to `.env` (already done if `.env` exists) and set your keys:

- `DEEPSEEK_API_KEY`: Your model API key.
- `SECRET_KEY`: A long random string for JWT security.
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`: For Google Auth integration.
- `APP_PORT`: Local server port (default `8000`). Change this if `8000` is already in use.
- `LLM_TIMEOUT_SECONDS`: Timeout for model API calls (default `45`).
- `LLM_MAX_RETRIES`: Number of automatic retries for transient API failures (default `2`).
- `SNWOLLEY_API_KEY`: Platform key used as the `X-APIKey` header when proxying Snwolley APIs.
- `SNWOLLEY_CHAT_COMPLETIONS_URL`: Chat completions URL (default `https://v1.snwolley.ai/v1/chat/completions`).
- `SNWOLLEY_HACKATHON_BASE_URL`: Base URL for hackathon APIs (default `https://v1.snwolley.ai/api/v1/hackathon`).
- `SNWOLLEY_TIMEOUT_SECONDS`: Timeout for Snwolley proxy requests (default `90`).
- `VERIFY_SSL`: Keep `true` for normal use. For local SSL troubleshooting only, set `false`.

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
- **Twi Language Support**: Automatic detection and translation for Ghanaian users.
- **RAG Implementation**: AI answers are grounded in 160+ pages of clinical guidelines (`.pdf`).
- **Pharmacist Dashboard**: Licensed professionals can review pending cases.
- **Body Map**: Interactive visual tool for selecting symptom areas.

## Snwolley API Proxy Endpoints

The backend now exposes pass-through routes that inject `X-APIKey` using `SNWOLLEY_API_KEY`:

- `POST /api/snwolley/chat/completions` → `https://v1.snwolley.ai/v1/chat/completions`
- `POST /api/snwolley/hackathon` → `https://v1.snwolley.ai/api/v1/hackathon`
- `POST /api/snwolley/stt` → `https://v1.snwolley.ai/api/v1/hackathon/stt`
- `POST /api/snwolley/tts` → `https://v1.snwolley.ai/api/v1/hackathon/tts`
- `POST /api/snwolley/vision` → `https://v1.snwolley.ai/api/v1/hackathon/vision`

## Security & Ethics

- BisaRx does NOT prescribe medication directly.
- All AI summaries MUST be reviewed by a human pharmacist.
- Patient data is stored securely using bcrypt hashing and JWT.
