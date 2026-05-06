#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# Skylar IQ QA Tool — one-shot Azure deployment.
#
# Provisions: Resource Group · Postgres Flexible Server · ACR · Storage
# Account / File Share · Container Apps environment · the running app.
#
# Pre-reqs:
#   1. Azure CLI installed:  https://learn.microsoft.com/cli/azure/install-azure-cli
#   2. Logged in:            az login
#   3. Docker daemon running locally (used by `az acr build` to upload context).
#
# Usage:
#   ./deploy/azure-deploy.sh
#
# Idempotent: re-running uses existing resources (won't recreate a Postgres if
# one with the same name already exists).
# ----------------------------------------------------------------------------
set -euo pipefail

# ---- Tunables --------------------------------------------------------------
RG="${SQA_RG:-skylar-qa-rg}"
LOCATION="${SQA_LOCATION:-eastus}"
ACR="${SQA_ACR:-skylarqa$(date +%s | tail -c 6)}"   # must be globally unique
PG="${SQA_PG:-skylar-qa-db-$(date +%s | tail -c 6)}"
PG_USER="${SQA_PG_USER:-skylar}"
PG_DB="${SQA_PG_DB:-skylar}"
STORAGE="${SQA_STORAGE:-skylarqasa$(date +%s | tail -c 6)}"
SHARE="${SQA_SHARE:-skylar-runs}"
ENV="${SQA_ENV:-skylar-qa-env}"
APP="${SQA_APP:-skylar-qa}"
IMAGE_TAG="${SQA_IMAGE_TAG:-latest}"
CPU="${SQA_CPU:-1.0}"
MEMORY="${SQA_MEMORY:-2.0Gi}"

# ---- Inputs ----------------------------------------------------------------
echo
echo "Skylar IQ QA Tool — Azure deploy"
echo "================================="
echo
echo "Resource group:  $RG"
echo "Region:          $LOCATION"
echo "Postgres server: $PG"
echo "ACR:             $ACR"
echo "Storage:         $STORAGE  (share: $SHARE)"
echo "Container App:   $APP  (env: $ENV)"
echo
read -srp "Postgres admin password (will be set on the new Flexible Server, 8+ chars): " PG_PASSWORD; echo
if [ ${#PG_PASSWORD} -lt 8 ]; then echo "Password too short."; exit 1; fi
read -p "Continue? [y/N] " ans
[[ "${ans:-n}" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

az account show >/dev/null 2>&1 || { echo "Run 'az login' first."; exit 1; }

# ---- 1. Resource group -----------------------------------------------------
echo
echo "==> [1/9] Resource group"
az group create -n "$RG" -l "$LOCATION" --output none

# ---- 2. Postgres Flexible Server -------------------------------------------
echo "==> [2/9] Postgres Flexible Server (this is the slowest step, ~3 min)"
if az postgres flexible-server show -g "$RG" -n "$PG" >/dev/null 2>&1; then
  echo "    server already exists — skipping create"
else
  az postgres flexible-server create \
    --resource-group "$RG" --name "$PG" --location "$LOCATION" \
    --admin-user "$PG_USER" --admin-password "$PG_PASSWORD" \
    --sku-name Standard_B1ms --tier Burstable \
    --version 16 --storage-size 32 \
    --public-access 0.0.0.0 --yes --output none
fi
az postgres flexible-server db create \
  --resource-group "$RG" --server-name "$PG" --database-name "$PG_DB" \
  --output none 2>/dev/null || true
PG_HOST=$(az postgres flexible-server show -g "$RG" -n "$PG" --query fullyQualifiedDomainName -o tsv)
DATABASE_URL="postgresql://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:5432/${PG_DB}?sslmode=require"
echo "    DATABASE_URL set (host: $PG_HOST)"

# ---- 3. Container Registry -------------------------------------------------
echo "==> [3/9] Azure Container Registry"
az acr create -g "$RG" -n "$ACR" --sku Basic --admin-enabled true --output none
ACR_LOGIN_SERVER=$(az acr show -g "$RG" -n "$ACR" --query loginServer -o tsv)
ACR_USER=$(az acr credential show -g "$RG" -n "$ACR" --query username -o tsv)
ACR_PASS=$(az acr credential show -g "$RG" -n "$ACR" --query 'passwords[0].value' -o tsv)
echo "    registry: $ACR_LOGIN_SERVER"

# ---- 4. Build + push image -------------------------------------------------
echo "==> [4/9] Build + push image (uses Azure-side build, ~3 min)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
az acr build --registry "$ACR" --image "skylar-qa:${IMAGE_TAG}" "$ROOT" --output none
IMAGE_FULL="${ACR_LOGIN_SERVER}/skylar-qa:${IMAGE_TAG}"
echo "    image: $IMAGE_FULL"

# ---- 5. Storage account + File Share ---------------------------------------
echo "==> [5/9] Storage account + File Share for /app/runs persistence"
az storage account create -g "$RG" -n "$STORAGE" -l "$LOCATION" \
  --sku Standard_LRS --kind StorageV2 --output none
STORAGE_KEY=$(az storage account keys list -g "$RG" -n "$STORAGE" --query '[0].value' -o tsv)
az storage share-rm create -g "$RG" --storage-account "$STORAGE" \
  --name "$SHARE" --quota 5 --enabled-protocols SMB --output none

# ---- 6. Container Apps environment -----------------------------------------
echo "==> [6/9] Container Apps environment"
if ! az containerapp env show -g "$RG" -n "$ENV" >/dev/null 2>&1; then
  az containerapp env create -g "$RG" -n "$ENV" -l "$LOCATION" --output none
fi

# ---- 7. Mount File Share into env -----------------------------------------
echo "==> [7/9] Bind File Share to Container Apps env"
az containerapp env storage set -g "$RG" -n "$ENV" \
  --storage-name skylar-runs-mount \
  --azure-file-account-name "$STORAGE" \
  --azure-file-account-key "$STORAGE_KEY" \
  --azure-file-share-name "$SHARE" \
  --access-mode ReadWrite --output none 2>/dev/null || true

# ---- 8. Deploy / update the Container App ----------------------------------
echo "==> [8/9] Deploy Container App"
SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || python3 -c 'import secrets;print(secrets.token_hex(32))')

if az containerapp show -g "$RG" -n "$APP" >/dev/null 2>&1; then
  echo "    app exists — updating image + env vars"
  az containerapp update -g "$RG" -n "$APP" \
    --image "$IMAGE_FULL" \
    --set-env-vars \
      DATABASE_URL="$DATABASE_URL" \
      SQA_SECRET_KEY="$SECRET_KEY" \
      SQA_ALLOW_SIGNUP=true \
    --output none
else
  az containerapp create \
    -g "$RG" -n "$APP" --environment "$ENV" \
    --image "$IMAGE_FULL" \
    --target-port 5050 --ingress external \
    --registry-server "$ACR_LOGIN_SERVER" \
    --registry-username "$ACR_USER" --registry-password "$ACR_PASS" \
    --cpu "$CPU" --memory "$MEMORY" \
    --min-replicas 1 --max-replicas 1 \
    --env-vars \
      DATABASE_URL="$DATABASE_URL" \
      SQA_SECRET_KEY="$SECRET_KEY" \
      SQA_ALLOW_SIGNUP=true \
    --output none
fi

# ---- 9. Wire up volume mount -----------------------------------------------
echo "==> [9/9] Mount File Share into the app at /app/runs"
# Container Apps volume mounts are configured via revision YAML — patch it.
TMP_YAML=$(mktemp)
az containerapp show -g "$RG" -n "$APP" -o yaml > "$TMP_YAML"
python3 - <<PY
import yaml, sys
with open("$TMP_YAML") as f: d = yaml.safe_load(f)
tmpl = d.setdefault('properties', {}).setdefault('template', {})
tmpl.setdefault('volumes', [])
if not any(v.get('name') == 'runs-vol' for v in tmpl['volumes']):
    tmpl['volumes'].append({
        'name': 'runs-vol', 'storageType': 'AzureFile',
        'storageName': 'skylar-runs-mount',
    })
for c in tmpl.get('containers', []):
    c.setdefault('volumeMounts', [])
    if not any(m.get('volumeName') == 'runs-vol' for m in c['volumeMounts']):
        c['volumeMounts'].append({'volumeName': 'runs-vol', 'mountPath': '/app/runs'})
with open("$TMP_YAML", 'w') as f: yaml.safe_dump(d, f)
PY
az containerapp update -g "$RG" -n "$APP" --yaml "$TMP_YAML" --output none
rm -f "$TMP_YAML"

# ---- Done ------------------------------------------------------------------
URL=$(az containerapp show -g "$RG" -n "$APP" --query 'properties.configuration.ingress.fqdn' -o tsv)
cat <<EOF

================================================================
✅ Deploy complete

  Open:                   https://$URL/
  Sign up at:             https://$URL/signup

  Postgres host:          $PG_HOST
  Database URL stored as Container App env var: DATABASE_URL

To redeploy the latest local code:
  az acr build --registry $ACR --image skylar-qa:latest .
  az containerapp update -g $RG -n $APP --image $ACR_LOGIN_SERVER/skylar-qa:latest

To lock public signup down:
  az containerapp update -g $RG -n $APP --set-env-vars SQA_ALLOW_SIGNUP=false

To tear everything down (irreversibly):
  az group delete -n $RG --yes
================================================================
EOF
