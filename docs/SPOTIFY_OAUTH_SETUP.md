# Spotify OAuth Setup

## Setup

### 1. Create a Spotify Developer App

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Sign in and click **Create App**
3. Fill in:
   - **App Name**: Dopetracks
   - **App Description**: Personal playlist creator
   - **Redirect URI**: `http://127.0.0.1:8888/callback`
4. Save, then copy your **Client ID** and **Client Secret**

### 2. Configure Environment

Add your credentials to the `.env` file in the project root:

```bash
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

**Important:** Use `127.0.0.1`, not `localhost`. Spotify requires explicit loopback IP addresses.

### 3. Restart the Backend

If the backend is already running, restart it to pick up the new `.env` values.

## Troubleshooting

### "INVALID_CLIENT: Insecure redirect URI"

Your redirect URI doesn't match what's in the Spotify Dashboard. Check that all three match exactly:
1. Spotify Developer Dashboard redirect URI
2. `SPOTIFY_REDIRECT_URI` in `.env`
3. No trailing slash

```
Good:  http://127.0.0.1:8888/callback
Bad:   http://localhost:8888/callback
Bad:   http://127.0.0.1:8888/callback/
```

### "INVALID_CLIENT: Invalid redirect URI"

The redirect URI isn't registered in your Spotify Dashboard. Add `http://127.0.0.1:8888/callback` under **Edit Settings > Redirect URIs**.

### Authorization Succeeds but Tokens Aren't Saved

Check the backend logs (`backend.log`) for errors during the callback. Common causes:
- Database write failure (check `~/.dopetracks/local.db` permissions)
- Expired authorization code (retry the flow)

## Checklist

- [ ] Spotify Developer App created
- [ ] Redirect URI set to `http://127.0.0.1:8888/callback` in Dashboard
- [ ] `.env` has `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI`
- [ ] Using `127.0.0.1` (not `localhost`)
- [ ] No trailing slash on redirect URI
- [ ] Backend restarted after `.env` changes

## See Also

- [Spotify Authorization Guide](https://developer.spotify.com/documentation/web-api/concepts/authorization)
- [Testing Guide](./TESTING.md)
- [Quick Start Guide](../QUICK_START.md)
