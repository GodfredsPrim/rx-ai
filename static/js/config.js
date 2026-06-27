// Frontend uses same-origin API by default ("/api", "/ws").
// For hosts like Vercel, vercel.json rewrites proxy requests to the backend.
// Override this only if you need to point directly to a remote backend.
window.BISARX_API_URL = '';
