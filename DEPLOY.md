# Deployment guide — Remote GA4 MCP server

This guide covers deploying the OAuth-protected Google Analytics MCP server on
a self-hosted host running Portainer and Nginx Proxy Manager (NPM).

---

## 1. Fork the repository

Fork your fork of this repo to a private or public repository under your own
account. Portainer's Git stack will pull from that fork.

---

## 2. Create a Google Cloud OAuth client

1. Open [Google Cloud Console](https://console.cloud.google.com/) and select or
   create a project.
2. Enable the following APIs:
   - **Google Analytics Admin API**
   - **Google Analytics Data API**
3. Go to **APIs & Services → Credentials → Create credentials → OAuth client ID**.
4. Application type: **Web application**.
5. Add an **Authorized redirect URI**:
   ```
   https://<your-host>/oauth/callback
   ```
6. Note the **Client ID** and **Client Secret** — you will set them as stack
   environment variables.

> Scopes required: `openid`, `email`, `https://www.googleapis.com/auth/analytics.readonly`
> (the server requests these automatically; no manual scope addition is needed in
> the OAuth consent screen beyond the Analytics readonly scope).

---

## 3. Deploy with Portainer (Git stack)

### 3a. Create the stack

1. In Portainer, go to **Stacks → Add stack**.
2. Choose **Repository**.
3. Set the repository URL to your fork and the branch to `remote-oauth-mcp` (or
   whichever branch you deployed to).
4. Set the compose file path to:
   ```
   docker-compose.portainer.yml
   ```
5. Enable **GitOps auto-update** if you want automatic redeploys on push.

### 3b. Set environment variables

In the stack's **Environment** section, set at minimum:

| Variable | Description |
|---|---|
| `GOOGLE_CLIENT_ID` | OAuth client ID from step 2 |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret from step 2 |
| `JWT_SECRET` | Random secret (`openssl rand -base64 32`) |
| `BASE_URL` | Your public HTTPS URL, e.g. `https://<your-host>` |
| `ALLOWED_GOOGLE_DOMAINS` | Comma-separated Google Workspace domains (e.g. `example.com`). Leave empty for open mode (not recommended). |
| `ALLOWED_EMAILS` | Optional comma-separated emails outside the domain list |
| `ACCESS_TOKEN_TTL_SECONDS` | Access-token lifetime in seconds (default `86400` = 24 h) |
| `TRUST_PROXY` | `true` when behind NPM (enables `X-Forwarded-For` for rate limiting) |
| `LOG_LEVEL` | `info` (default) or `debug` |

> Do NOT commit real values for these variables. The compose file reads them from
> the Portainer stack environment — nothing sensitive ever lives in this repo.

### 3c. Ensure the external `docker_bridge` network exists

The compose file references an external network named `docker_bridge`. Create it
once on the host if it does not already exist:

```bash
docker network create docker_bridge
```

---

## 4. Configure Nginx Proxy Manager

1. In NPM, add a new **Proxy Host**:
   - **Domain Names:** `<your-host>`
   - **Scheme:** `http`
   - **Forward Hostname/IP:** `mcp-google-analytics`
   - **Forward Port:** `8080`
   - **Websockets Support:** ON
2. Enable **SSL** (Let's Encrypt or your own certificate), and **Force SSL**.
3. Set `BASE_URL=https://<your-host>` in the Portainer stack environment (the
   value must match the public URL exactly, without a trailing slash).
4. Set `TRUST_PROXY=true` in the stack environment, and make sure the proxy
   forwards `X-Forwarded-Proto` (in NPM "advanced"/enhanced builds, enable
   **"trust upstream forwarded proto headers"**). The app trusts these headers
   (uvicorn `proxy_headers`), so it sees the original `https` scheme. Without
   this, the `/mcp` → `/mcp/` redirect downgrades to `http://` and the Claude
   handshake breaks.
5. **Streaming (SSE):** MCP responses are streamed as `text/event-stream`. If
   tool calls hang, disable proxy buffering and raise the read timeout. In
   vanilla NPM, paste into the proxy host **Advanced → Custom Nginx
   Configuration**:
   ```nginx
   proxy_buffering off;
   proxy_read_timeout 3600s;
   ```

> **Note on the `/mcp` redirect:** a request to `/mcp` returns a `307` redirect
> to `/mcp/`; MCP clients (including Claude) follow it automatically. This is
> expected — just ensure the scheme stays `https` (step 4).

> **Cloudflare note:** if your domain is proxied through Cloudflare (orange
> cloud), the proxy can buffer SSE and impose request timeouts that interfere
> with streaming, and Let's Encrypt HTTP-01 challenges must reach NPM. For the
> simplest setup, set this subdomain to **DNS-only (grey cloud)**.

---

## 5. Connect Claude

1. In Claude, open **Settings → Connectors → Add custom connector**.
2. Enter the MCP endpoint URL:
   ```
   https://<your-host>/mcp
   ```
3. Claude will open the Google sign-in flow. Sign in with a Google account that
   matches `ALLOWED_GOOGLE_DOMAINS` or `ALLOWED_EMAILS`.
4. After the first sign-in the session is persisted in the `/data/tokens.db`
   volume; subsequent connections within the token TTL require no re-authentication.

---

## 6. Verify the deployment

Run these checks from any machine with `curl` access:

```bash
# Should return {"status":"healthy","service":"analytics-mcp"}
curl https://<public-host>/health

# Should return OAuth protected-resource metadata (RFC 9728)
curl https://<public-host>/.well-known/oauth-protected-resource

# Should return HTTP 401 with a WWW-Authenticate header (auth required)
curl -i -X POST https://<public-host>/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

---

## 7. Syncing with upstream

To pull in upstream changes from the original repository:

```bash
git fetch upstream
git rebase upstream/main
git push origin remote-oauth-mcp
```

Portainer will pick up the update automatically if GitOps auto-update is enabled.
