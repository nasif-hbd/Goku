# Deploying Steward — start to finish

No local installation required. Everything below runs in **Google Cloud Shell**,
a browser terminal with `gcloud`, `git`, and Python already installed.

Budget about 20 minutes. Expected cost: effectively zero — Cloud Run, Firestore,
and Gemini all have free tiers that this workload sits inside. A billing account
must still be attached, because Google requires one before these APIs can be
enabled.

---

## 1. Get a Gemini API key

Go to **<https://aistudio.google.com/apikey>**, sign in, and click
**Create API key**. Copy it somewhere safe — you cannot view it again later.

This is the key that satisfies the competition's Gemini requirement. Without it
the app still runs, but every decision falls back to templates and the dashboard
says so.

## 2. Create a Google Cloud project

Go to **<https://console.cloud.google.com/projectcreate>**, name the project
(for example `steward-app`), and create it. Note the **Project ID** — it is
usually the name plus some digits, and it is what the deploy script needs.

Then attach billing: **<https://console.cloud.google.com/billing>** → link a
billing account to the project. A card is required; the free tiers mean you
should not be charged for this workload, but do set a budget alert if you want
certainty.

## 3. Open Cloud Shell

Go to **<https://shell.cloud.google.com>**. A terminal opens in the browser.
Click **Authorize** if it asks.

## 4. Deploy

Paste these in, replacing the two placeholder values:

```bash
git clone https://github.com/nasif-hbd/Goku.git
cd Goku

export PROJECT_ID=your-project-id-here
export GEMINI_API_KEY=your-gemini-key-here

./deploy/deploy.sh
```

The script enables the required APIs, creates the Firestore database, stores the
key in Secret Manager, builds the container, deploys it to Cloud Run, and
schedules the agents to run every four hours.

It prints your live URL at the end. It looks like
`https://steward-xxxxxxxx-uc.a.run.app`.

If it stops on an API-enablement error, it is usually billing not yet being
active on the project. Attach billing, then run the script again — it is safe to
re-run.

## 5. Load the demo data and run the agents

A fresh deployment has an empty database. Seed it once, then run a tick:

```bash
URL=$(gcloud run services describe steward --region us-central1 --format='value(status.url)')

curl -X POST $URL/seed     # one-time; refuses if data already exists
curl -X POST $URL/tick     # runs all five agents now
echo $URL
```

Open the URL. You should see the decision log filling up, with real Gemini model
names and latencies in the model column rather than `fallback:*`.

Run `curl -X POST $URL/tick` twice more to watch escalation play out: nudge,
second nudge, hand to the owner, then silence.

## 6. Confirm before recording anything

```bash
curl $URL/healthz
```

Check that `"gemini_configured": true` and `"store": "firestore"`. If
`gemini_configured` is false the key did not reach the container, and the demo
video will visibly show template output instead of Gemini output.

---

## Afterwards

- **Live app:** the Cloud Run URL — this is what goes in the submission.
- **Evidence:** Cloud Scheduler job history proves the agents run unattended;
  the Gemini API request graph in the console proves the calls are real. See
  `EVIDENCE.md`.
- **Video:** `DEMO_SCRIPT.md`, recorded against the Cloud Run URL, not localhost.

## Taking it down

```bash
gcloud run services delete steward --region us-central1
gcloud scheduler jobs delete steward-tick --location us-central1
```

Or delete the whole project at
<https://console.cloud.google.com/iam-admin/settings>, which stops everything at
once.
