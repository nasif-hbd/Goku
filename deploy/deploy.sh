#!/usr/bin/env bash
# Deploy Steward to Cloud Run with Firestore and Cloud Scheduler.
#
# Google Cloud products used (satisfies the competition's Google Cloud requirement):
#   - Cloud Run          hosts the application
#   - Firestore          stores orgs, clients, decisions, messages
#   - Cloud Scheduler    invokes /tick so the agents run unattended
#   - Secret Manager     holds the Gemini API key
#
# Prerequisites: gcloud CLI authenticated, billing enabled, a Gemini API key.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-steward}"
TICK_SCHEDULE="${TICK_SCHEDULE:-0 */4 * * *}"   # every 4 hours

echo "==> Project: $PROJECT_ID  Region: $REGION  Service: $SERVICE"
gcloud config set project "$PROJECT_ID" >/dev/null

echo "==> Enabling APIs"
gcloud services enable \
  run.googleapis.com \
  firestore.googleapis.com \
  cloudscheduler.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com

echo "==> Ensuring Firestore database exists"
if ! gcloud firestore databases describe --database='(default)' >/dev/null 2>&1; then
  gcloud firestore databases create --location="$REGION"
else
  echo "    already exists"
fi

echo "==> Storing Gemini API key in Secret Manager"
if [ -n "${GEMINI_API_KEY:-}" ]; then
  if gcloud secrets describe gemini-api-key >/dev/null 2>&1; then
    printf '%s' "$GEMINI_API_KEY" | gcloud secrets versions add gemini-api-key --data-file=-
  else
    printf '%s' "$GEMINI_API_KEY" | gcloud secrets create gemini-api-key --data-file=-
  fi
else
  echo "    GEMINI_API_KEY not set - assuming the secret already exists"
fi

RUNTIME_SA="$(gcloud iam service-accounts list \
  --filter="email ~ ^${PROJECT_ID//:/}-compute@" --format='value(email)' | head -1)"
if [ -n "$RUNTIME_SA" ]; then
  gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role=roles/secretmanager.secretAccessor >/dev/null 2>&1 || true
fi

echo "==> Building and deploying to Cloud Run"
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},STEWARD_VERTICAL=${STEWARD_VERTICAL:-coaching_center},GEMINI_MODEL=${GEMINI_MODEL:-gemini-2.5-flash},STEWARD_CURRENCY=${STEWARD_CURRENCY:-USD}" \
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest"

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
echo "==> Live at $URL"

echo "==> Scheduling agent ticks ($TICK_SCHEDULE)"
if gcloud scheduler jobs describe steward-tick --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http steward-tick \
    --location "$REGION" --schedule "$TICK_SCHEDULE" --uri "${URL}/tick" --http-method POST
else
  gcloud scheduler jobs create http steward-tick \
    --location "$REGION" --schedule "$TICK_SCHEDULE" --uri "${URL}/tick" --http-method POST
fi

echo
echo "Done."
echo "  Dashboard:  $URL"
echo "  Health:     $URL/healthz"
echo "  Force tick: curl -X POST $URL/tick"
