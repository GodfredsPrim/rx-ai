# RxAI Ghana Full System

This project turns your `rxai-ghana.html` prototype into a full-stack working system with:

- Secure auth (`JWT + bcrypt`)
- Persistent patient data (`SQLite`)
- Medication management (add/remove)
- Emergency contacts
- AI chat via backend proxy (Anthropic API key kept server-side)

## Tech stack

- Frontend: vanilla HTML/CSS/JS (`public/`)
- Backend: Node.js + Express (`src/server.js`)
- Database: SQLite (`data.sqlite`)

## 1) Install dependencies

```bash
npm install
```

## 2) Configure environment

Copy `.env.example` to `.env` and set values:

```env
PORT=3000
JWT_SECRET=replace-with-a-long-random-secret
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

## 3) Run

```bash
npm start
```

Open: `http://localhost:3000`

## API summary

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/me`
- `PUT /api/me/profile`
- `PUT /api/me/medical`
- `PUT /api/me/emergency`
- `POST /api/me/medications`
- `DELETE /api/me/medications/:id`
- `POST /api/chat`
- `GET /api/health`

## Security notes

- Never expose API keys in frontend code.
- Change `JWT_SECRET` in production.
- Add HTTPS + rate limiting before public deployment.
