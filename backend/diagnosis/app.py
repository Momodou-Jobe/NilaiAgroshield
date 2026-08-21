import json
import os

import boto3
from flask import Flask, Response, request, stream_with_context

app = Flask(__name__)

# Global cross-region inference profile. The "global." prefix routes worldwide
# for maximum throughput, so IAM must allow "*" for the region.
MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

# Bedrock runtime client. Region is picked up from the Lambda execution
# environment; the cross-region profile handles routing to us-east-2/us-west-2.
bedrock = boto3.client("bedrock-runtime")

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

SYSTEM_PROMPT = (
    "You are AgroShield AI, a friendly and knowledgeable agricultural assistant "
    "that helps smallholder farmers. Diagnose crop diseases and pest problems, "
    "give tailored treatment recommendations (both organic and chemical options), "
    "and teach simple preventive farming practices.\n\n"
    "Write in plain, non-technical language a farmer without a scientific "
    "background can easily understand. Be warm, encouraging, and practical. "
    "Factor in the farm location and recent weather conditions to make advice "
    "locally relevant. If a photo is provided, use it to improve accuracy.\n\n"
    "Structure your response using markdown with these sections:\n"
    "## Likely Diagnosis\n"
    "## Why This Is Happening\n"
    "## Organic Treatment\n"
    "## Chemical Treatment\n"
    "## Prevention Tips\n"
    "## When To Seek Local Help\n\n"
    "Use bullet points and short sentences. Always remind farmers to confirm "
    "with a local agricultural extension officer before applying chemicals."
)


def build_prompt(data):
    """Turn the incoming form fields into a readable prompt for the model."""
    crop = data.get("crop_name", "").strip() or "not specified"
    age = data.get("crop_age", "").strip() or "not specified"
    part = data.get("plant_part", "").strip() or "not specified"
    symptoms = data.get("symptoms", "").strip() or "not described"
    field_pct = data.get("field_percentage", "").strip() or "not specified"
    weather = data.get("weather", "").strip() or "not specified"
    pests = data.get("pests", "").strip()
    treatments = data.get("treatments", "").strip()
    location = data.get("location", "").strip() or "not specified"

    lines = [
        "A farmer needs help diagnosing a crop problem. Here are the details:",
        "",
        f"- Crop name and variety: {crop}",
        f"- Crop age (weeks): {age}",
        f"- Plant part affected: {part}",
        f"- Symptoms observed: {symptoms}",
        f"- Percentage of field affected: {field_pct}%",
        f"- Recent weather conditions: {weather}",
        f"- Farm location: {location}",
    ]

    if pests:
        lines.append(f"- Pest or insect observations: {pests}")
    else:
        lines.append("- Pest or insect observations: none reported")

    if treatments:
        lines.append(f"- Recent treatments applied: {treatments}")
    else:
        lines.append("- Recent treatments applied: none reported")

    lines.append("")
    lines.append(
        "Please provide a full diagnosis and actionable recommendations."
    )
    return "\n".join(lines)


def build_messages(data):
    """Build the Bedrock messages list, prepending an image/document block
    when the request carries file_data + file_mime."""
    prompt_text = build_prompt(data)
    content = []

    file_data = data.get("file_data")
    file_mime = data.get("file_mime")

    if file_data and file_mime:
        if file_mime.startswith("image/"):
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": file_mime,
                        "data": file_data,
                    },
                }
            )
        else:
            # Non-image uploads become a document block.
            content.append(
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": file_mime,
                        "data": file_data,
                    },
                }
            )

    content.append({"type": "text", "text": prompt_text})

    return [{"role": "user", "content": content}]


@app.route("/", methods=["OPTIONS"])
def options():
    return Response(status=200, headers=CORS_HEADERS)


@app.route("/", methods=["POST"])
def diagnose():
    data = request.get_json(silent=True) or {}
    messages = build_messages(data)

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "temperature": 0.4,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }

    def generate():
        try:
            response = bedrock.invoke_model_with_response_stream(
                modelId=MODEL_ID,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            for event in response["body"]:
                chunk = event.get("chunk")
                if not chunk:
                    continue
                payload = json.loads(chunk["bytes"].decode("utf-8"))
                if payload.get("type") == "content_block_delta":
                    delta = payload.get("delta", {})
                    text = delta.get("text")
                    if text:
                        yield text
        except Exception as exc:  # noqa: BLE001 - surface any error to the client
            yield f"\n\n[Error generating diagnosis: {exc}]"

    return Response(
        stream_with_context(generate()),
        content_type="text/plain; charset=utf-8",
        headers=CORS_HEADERS,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
