# AgroShield AI — Crop Disease Diagnostic Tool

An intelligent farming companion for smallholder farmers. Farmers describe their
crop and symptoms (and optionally upload a photo), and an AI agricultural
assistant streams back a plain-language diagnosis with organic and chemical
treatment options plus prevention tips.

Built on **AWS Lambda + API Gateway (Function URLs) + Amazon Bedrock + S3**,
deployed with **AWS SAM** and **GitHub Actions**.

## Architecture

```
frontend/  (S3 static website)  --POST-->  DiagnosisFunction (streaming Flask Lambda)
                                                     |
                                                     v
                                     Amazon Bedrock (Claude Haiku 4.5,
                                     global cross-region inference profile)
```

- **frontend/** — single-page app (HTML/CSS/JS). Mirrors 10 input widgets,
  streams the diagnosis token-by-token, renders markdown per line, and supports
  drag-and-drop photo upload (sent as base64).
- **backend/diagnosis/** — Flask app run via the AWS Lambda Web Adapter. Streams
  the Bedrock response with `invoke_model_with_response_stream`. Adds a
  multimodal image block when a photo is uploaded.
- **infra/template.yaml** — AWS SAM template: IAM role, streaming Lambda Function
  URL, and public-read S3 website bucket.
- **.github/workflows/deploy.yml** — builds and deploys with SAM, injects the
  Function URL into the frontend, and syncs to S3.

## Deploy

### Prerequisites

1. **GitHub repository secrets** (Settings -> Secrets and variables -> Actions):
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `SAM_DEPLOY_BUCKET` — an existing S3 bucket in `ap-southeast-1` used by SAM
     for packaging artifacts.
2. **Enable Bedrock model access** for
   `global.anthropic.claude-haiku-4-5-20251001-v1:0`
   (Claude Haiku 4.5 — global cross-region inference profile) in `ap-southeast-1`
   via AWS Console -> Bedrock -> Model Access. First-time accounts must submit
   the use-case form.

### Run

Push to `main` (or trigger the workflow manually). When the workflow completes,
the run summary prints the live **Website URL**.

## Local development

```bash
cd backend/diagnosis
pip install -r requirements.txt
python app.py            # serves on http://localhost:8080
```

The frontend can be opened directly in a browser for layout work; live diagnosis
requires the deployed Function URL (injected into `app.js` during deployment).

## The team

AgroShield is supported by an agronomy team spanning plant pathology, soil
science, and pest management. Always confirm treatments with a local
agricultural extension officer before applying chemicals.
