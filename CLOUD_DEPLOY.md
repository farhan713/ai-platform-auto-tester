# Cloud deployment guide

The tool is a stateful Flask + Playwright + Postgres app. It needs:

- **At least 1 GB RAM** for the app (Chromium is heavy). 2 GB is comfortable.
- **A managed Postgres** instance (or the bundled `db` service from `docker-compose.yml`). All user accounts, runs, presets, and per-query results live there.
- **A persistent volume** for `/app/runs/` and `/app/data/` (screenshots, REPORT.html, uploaded xlsx files — these are too large for the DB).
- **HTTPS** — every recommended provider gives this for free.
- **Required env vars**:
  - `DATABASE_URL` (or `PGHOST`/`PGUSER`/`PGPASSWORD`/`PGDATABASE`)
  - `SQA_SECRET_KEY` (random 32+ byte hex; signs session cookies)
  - `SQA_ALLOW_SIGNUP=false` once your team has accounts (recommended)

> **First user to sign up becomes admin.** Open `https://your-deployment.example.com/signup` and create your admin account immediately after deploy — before anyone else can grab it.

> **Network reachability check first.** The container has to be able to reach the Celerant tenant URLs you test against. If those URLs are inside a client's VPN, a public cloud server cannot reach them — you'd need a self-hosted VM on the client's network instead.

---

## Option 1 — Render.com (easiest, ~10 minutes)

1. Push this repo to GitHub/GitLab.
2. In [Render dashboard](https://dashboard.render.com/) → **New → Blueprint** → connect the repo. It picks up `render.yaml` and creates the web service + 5 GB disk.
3. **Add a Postgres database** separately: New → PostgreSQL → Free tier (or Starter for production). Render gives you a `DATABASE_URL`.
4. On the **Web Service → Environment** tab, set:
   - `DATABASE_URL` = the Internal Database URL Render shows you for the Postgres
   - `SQA_SECRET_KEY` = `openssl rand -hex 32`
   - `SQA_ALLOW_SIGNUP` = `true` initially (set to `false` after your admin signs up)
5. Render redeploys, gives you HTTPS at a `.onrender.com` URL.
6. **Visit `/signup` immediately** and create the admin account before anyone else can.
7. Set `SQA_ALLOW_SIGNUP=false` and save → service redeploys with public signup disabled.

**Cost:** $7/mo for the web Starter plan + $7/mo for Starter Postgres (or free Postgres tier for testing).

---

## Option 2 — Fly.io (more control, similar cost)

```
brew install flyctl       # or curl install
fly auth signup
fly launch                # picks up the Dockerfile, asks a few questions
fly volumes create skylar_data --region <yours> --size 5
fly secrets set SQA_AUTH_USER=admin SQA_AUTH_PASS=<long-random>
fly deploy
```

In `fly.toml` (Fly creates this for you), make sure:

```toml
[mounts]
  source = "skylar_data"
  destination = "/app/runs"

[[services]]
  internal_port = 5050
```

**Cost:** Free tier covers the smallest VM with 256 MB; you'll need to scale to `shared-cpu-1x` with 1024 MB (~$5/mo).

---

## Option 3 — DigitalOcean App Platform

1. New App → **Docker Hub** or **Container Registry** → point at your image.
2. Resources → set instance to **Basic / 1 GB RAM** ($12/mo).
3. Add an **App Volume** of 5 GB mounted at `/app/runs`.
4. Environment variables: `SQA_AUTH_USER`, `SQA_AUTH_PASS`.
5. Health check path: `/api/runs`.

---

## Option 4 — Microsoft Azure (Container Apps + Postgres Flexible Server)

Recommended Azure path — fully managed, scales to one or more replicas, billed per second.

### Quick start (one shell script)

The repo ships with [`deploy/azure-deploy.sh`](deploy/azure-deploy.sh) which provisions everything and prints your HTTPS URL at the end. You'll need the Azure CLI installed and `az login` done.

```bash
cd skylar-qa-tool
chmod +x deploy/azure-deploy.sh
deploy/azure-deploy.sh
```

The script asks for a **resource group**, **region**, and **Postgres password**, then creates:
- A resource group
- An Azure Database for PostgreSQL Flexible Server (Burstable B1ms, ~ \$13/mo)
- An Azure Container Registry (Basic tier, ~ \$5/mo)
- An Azure Storage Account + File Share for `/app/runs` persistence
- A Container Apps environment + the running app (1 vCPU / 2 GB RAM, ~ \$30/mo)
- A `DATABASE_URL` and random `SQA_SECRET_KEY`

It builds the image locally, pushes to ACR, and deploys. End-to-end ~10 minutes.

### Manual step-by-step

If you'd rather do it interactively, follow [`deploy/azure-deploy.sh`](deploy/azure-deploy.sh) line by line — every step is a single `az` command. The high-level flow:

| Step | Command |
|---|---|
| 1. Resource group | `az group create -n skylar-qa-rg -l eastus` |
| 2. Postgres Flexible Server | `az postgres flexible-server create ...` |
| 3. Postgres database | `az postgres flexible-server db create ...` |
| 4. Container Registry | `az acr create -n <name> --sku Basic` |
| 5. Build + push image | `az acr build --image skylar-qa:latest --registry <name> .` |
| 6. Storage account + File Share | `az storage account create ...` then `az storage share-rm create ...` |
| 7. Container Apps env | `az containerapp env create ...` |
| 8. Mount File Share into env | `az containerapp env storage set ...` |
| 9. Deploy the app | `az containerapp create ... --env-vars DATABASE_URL=... SQA_SECRET_KEY=...` |

### Sizing

| Component | Recommendation | Approx. \$/mo |
|---|---|---|
| Container App | 1 vCPU / 2 GiB, 1 replica min | \$30–40 |
| Postgres Flexible | Burstable B1ms, 32 GB storage | \$13 |
| ACR | Basic tier | \$5 |
| Storage (File Share) | Standard, 5 GB used | \$1 |
| **Total** | | **~\$50/month** |

### After deploy

1. Open the URL the script prints (something like `https://skylar-qa.<random>.eastus.azurecontainerapps.io`).
2. Sign up — first account becomes yours.
3. Once your team has signed up, set `SQA_ALLOW_SIGNUP=false` to lock down public registration:
   ```bash
   az containerapp update -n skylar-qa -g skylar-qa-rg \
     --set-env-vars SQA_ALLOW_SIGNUP=false
   ```

### Updating the deployed image

```bash
az acr build --image skylar-qa:latest --registry <your-acr> .
az containerapp update -n skylar-qa -g skylar-qa-rg \
  --image <your-acr>.azurecr.io/skylar-qa:latest
```

### Notes / gotchas

- **Outbound network reach**: the Container App must be able to reach the Celerant tenant URLs you test against. By default Container Apps egress goes out via Azure's egress IPs — verify with the client's IT if their tenant has IP allow-listing.
- **Postgres firewall**: the deploy script enables "Allow Azure services to access this server" so the Container App can connect. If you tighten that later, you'll need to whitelist the Container App's outbound IP or move Postgres into the same VNet.
- **Custom domain + HTTPS**: Container Apps gives you a free `*.azurecontainerapps.io` URL. To use your own domain: `az containerapp hostname add` + a managed cert (free).
- **Cold start**: Container Apps can scale to zero — but Playwright + Chromium take 5–10s to boot. Set `--min-replicas 1` (the script does) to keep it warm.

---

## Option 5 — Self-hosted VPS (DigitalOcean Droplet, AWS Lightsail, etc.)

Cheapest if you have multiple instances or want full control.

```bash
# On a fresh Ubuntu 22.04 droplet
ssh root@your-droplet-ip
apt-get update && apt-get install -y docker.io
git clone <your-repo> skylar-qa && cd skylar-qa
echo 'SQA_AUTH_USER=admin' > .env
echo 'SQA_AUTH_PASS=<long-random>' >> .env

# Adjust docker-compose.yml to load env vars (see below), then:
docker compose up -d
```

To get HTTPS, put **Caddy** in front:

```
# /etc/caddy/Caddyfile
qa.yourdomain.com {
  reverse_proxy localhost:5050
}
```

Caddy auto-issues Let's Encrypt certs.

---

## Verifying basic auth is on

```
curl -I https://your-deployment.example.com/
# expect: HTTP/1.1 401 Unauthorized

curl -I -u admin:<pass> https://your-deployment.example.com/
# expect: HTTP/1.1 200 OK
```

If the first command returns 200, **auth is OFF** — the env vars weren't picked up. Check provider dashboard.

---

## Sizing recommendations

| Concurrent jobs | RAM | Disk |
|---|---|---|
| 1 (typical) | 1 GB | 5 GB |
| 2–3 | 2 GB | 10 GB |
| Heavy use | 4 GB | 20 GB+ |

Each running Playwright Chromium uses ~400-700 MB. If you expect multiple concurrent runs, scale up.

---

## What to do if a deploy provider doesn't support persistent volumes

- Reports + saved test files will vanish on restart
- Workarounds: ship reports to S3 / Cloudflare R2 (a few extra lines of code we can add), or use a provider that does support volumes (all four above do)
