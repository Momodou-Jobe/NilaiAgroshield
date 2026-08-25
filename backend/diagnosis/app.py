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

# System prompt for the image gatekeeper. It must return ONLY strict JSON.
VALIDATION_SYSTEM_PROMPT = (
    "You are an image validation gate for a crop-diagnosis app. You are shown "
    "one photo and told which crop the farmer says it is. Judge the photo and "
    "reply with ONLY a single JSON object, no markdown, no extra text.\n\n"
    "The JSON must have exactly these keys:\n"
    '  "is_plant_part": boolean  — true only if the photo clearly shows a plant '
    "or a plant part (leaf, stem, root, flower, fruit, seed, whole plant, etc.). "
    "false for people, animals, objects, screenshots, scenery with no clear "
    "plant subject, etc.\n"
    '  "is_clear": boolean  — true only if the photo is sharp and well-lit '
    "enough to inspect for disease or pests. false if blurry, too dark, too "
    "bright/overexposed, too far away, or heavily obstructed.\n"
    '  "matches_crop": boolean  — true only if the plant in the photo is '
    "consistent with the crop the farmer named. If you cannot confidently tell "
    "the species, set this to true (do not block on uncertainty alone).\n"
    '  "detected_plant": string  — your best guess of the plant/crop in the '
    'photo, or "unknown".\n'
    '  "reason": string  — one short, friendly sentence for the farmer '
    "explaining the main problem if any check failed, written in simple "
    "non-technical language.\n\n"
    "Be practical, not overly strict: a normal phone photo of a real leaf in "
    "daylight should pass."
)

# System prompt for the location gatekeeper. It must return ONLY strict JSON.
LOCATION_SYSTEM_PROMPT = (
    "You check a farmer's stated farm location for a crop-diagnosis app. You "
    "judge two things: (1) whether crops can grow there, and (2) whether the "
    "text is a specific, named real place. Reply with ONLY a single JSON "
    "object, no markdown, no extra text.\n\n"
    "The JSON must have exactly these keys:\n"
    '  "can_grow": boolean  — false if the location is NOT on Earth (e.g. the '
    "Moon, Mars, the Sun, outer space, another planet), is fictional/made-up, "
    "or is a place where plants cannot realistically grow (e.g. open ocean, "
    "the deep sea, inside a volcano, the polar ice interior). true for any "
    "normal country, region, state, city, or farming area on Earth.\n"
    '  "is_specific": boolean  — true only if the text names an actual, '
    "identifiable place such as a country, state, province, region, district, "
    "city, or town (e.g. \"Kenya - Rift Valley\", \"Punjab, India\", "
    '"Kaduna, Nigeria"). false for vague, relative, or generic phrases that do '
    "not name a real place, such as \"here\", \"there\", \"my village\", "
    '"my farm", "home", "my place", "the field", "nearby", "over there", '
    '"our land", or a blank/gibberish entry.\n'
    '  "kind": string  — one of "earth_ok", "off_earth", "fictional", '
    '"uninhabitable", "too_vague", or "unclear".\n'
    '  "reason": string  — one short, friendly sentence for the farmer, in '
    "simple non-technical language, explaining the problem if can_grow is "
    "false OR is_specific is false. Empty string when both are true.\n\n"
    "Rules: A real named place where crops grow should have can_grow true, "
    'is_specific true, kind "earth_ok". A real named place that cannot grow '
    "crops uses the matching kind. A place that is on Earth and could grow "
    'crops but is only described vaguely (like "my village") should have '
    'can_grow true, is_specific false, kind "too_vague". When you truly '
    'cannot tell, set both true and kind "unclear" (do not block).'
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


def image_block(file_data, file_mime):
    """Build a Bedrock image/document content block from base64 data."""
    block_type = "image" if file_mime.startswith("image/") else "document"
    return {
        "type": block_type,
        "source": {
            "type": "base64",
            "media_type": file_mime,
            "data": file_data,
        },
    }


def build_messages(data):
    """Build the Bedrock messages list, prepending an image/document block
    when the request carries file_data + file_mime."""
    prompt_text = build_prompt(data)
    content = []

    file_data = data.get("file_data")
    file_mime = data.get("file_mime")

    if file_data and file_mime:
        content.append(image_block(file_data, file_mime))

    content.append({"type": "text", "text": prompt_text})

    return [{"role": "user", "content": content}]


def validate_image(file_data, file_mime, crop_name):
    """Run a quick, non-streaming gate over the uploaded photo.

    Returns a dict:
      {"ok": True}                          -> photo passed, proceed to diagnose
      {"ok": False, "message": "<text>"}    -> photo rejected, show message
    On any unexpected error we fail open (allow diagnosis) so a validation
    hiccup never blocks a legitimate farmer.
    """
    crop = crop_name.strip() or "the crop the farmer named"
    instruction = (
        f'The farmer says this photo is of: "{crop}". '
        "Validate the photo now and return ONLY the JSON object."
    )

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 400,
        "temperature": 0,
        "system": VALIDATION_SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": [
                    image_block(file_data, file_mime),
                    {"type": "text", "text": instruction},
                ],
            }
        ],
    }

    try:
        resp = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(resp["body"].read().decode("utf-8"))
        # Anthropic response: {"content": [{"type":"text","text":"..."}], ...}
        text = ""
        for block in payload.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
        verdict = _parse_json_object(text)
    except Exception:  # noqa: BLE001 - fail open on any validation error
        return {"ok": True}

    if verdict is None:
        # Could not read a verdict; don't block the farmer.
        return {"ok": True}

    is_plant = bool(verdict.get("is_plant_part", True))
    is_clear = bool(verdict.get("is_clear", True))
    matches = bool(verdict.get("matches_crop", True))
    detected = str(verdict.get("detected_plant", "") or "").strip()
    reason = str(verdict.get("reason", "") or "").strip()

    if is_plant and is_clear and matches:
        return {"ok": True}

    # Build a friendly, specific rejection message.
    if not is_plant:
        headline = "That photo does not look like a plant."
        detail = (
            "Please upload a clear photo of the affected plant part — for "
            "example a leaf, stem, root, flower, or fruit."
        )
    elif not is_clear:
        headline = "That photo is not clear enough to analyse."
        detail = (
            "Please take another photo that is sharp and well-lit. Get closer "
            "to the affected area, hold the camera steady, and avoid shadows, "
            "glare, or blur."
        )
    else:  # not matches
        seen = f' It looks more like {detected}.' if detected and detected.lower() != "unknown" else ""
        headline = (
            f'That photo does not match "{crop}".{seen}'
        )
        detail = (
            f'Please upload a photo of your {crop} plant part (leaf, stem, '
            "root, flower, or fruit) so the diagnosis stays accurate."
        )

    message = f"## Photo Not Accepted\n\n**{headline}**\n\n{detail}"
    if reason:
        message += f"\n\n*{reason}*"
    return {"ok": False, "message": message}


def validate_location(location):
    """Check whether the farm location is a real place on Earth where crops
    can grow.

    Returns a dict:
      {"ok": True}                          -> location fine, proceed
      {"ok": False, "message": "<text>"}    -> location rejected, show message
    Fails open (allows diagnosis) on any unexpected error or blank input so a
    validation hiccup never blocks a legitimate farmer.
    """
    loc = (location or "").strip()
    if not loc:
        # Location is required by the form; if empty, let the normal flow run.
        return {"ok": True}

    instruction = (
        f'The farmer entered this farm location: "{loc}". '
        "Judge it now and return ONLY the JSON object."
    )

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 300,
        "temperature": 0,
        "system": LOCATION_SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": instruction}]}
        ],
    }

    try:
        resp = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(resp["body"].read().decode("utf-8"))
        text = ""
        for block in payload.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
        verdict = _parse_json_object(text)
    except Exception:  # noqa: BLE001 - fail open on any validation error
        return {"ok": True}

    if verdict is None:
        return {"ok": True}

    can_grow = bool(verdict.get("can_grow", True))
    is_specific = bool(verdict.get("is_specific", True))
    kind = str(verdict.get("kind", "") or "").strip().lower()
    reason = str(verdict.get("reason", "") or "").strip()

    # Both checks passed -> proceed.
    if can_grow and is_specific:
        return {"ok": True}

    # A growable place that is only described vaguely ("here", "my village").
    if can_grow and not is_specific:
        headline = f'"{loc}" is not specific enough.'
        detail = (
            "Please enter an actual place instead of a general phrase like "
            '"here", "there", or "my village". Type your country and region '
            'or province — for example "Kenya - Rift Valley", '
            '"India - Punjab", or "Nigeria - Kaduna" — so we can tailor the '
            "advice to your local conditions."
        )
        message = f"## Location Not Accepted\n\n**{headline}**\n\n{detail}"
        if reason:
            message += f"\n\n*{reason}*"
        return {"ok": False, "message": message}

    if kind == "off_earth":
        headline = f'Plants cannot grow at "{loc}".'
        detail = (
            "That location is not on Earth. Crops need soil, air, water, and "
            "sunlight found only here on Earth. Please enter a real place on "
            "Earth — your country and region or province."
        )
    elif kind == "fictional":
        headline = f'"{loc}" does not appear to be a real place.'
        detail = (
            "We could not recognise that as a real location on Earth. Please "
            "enter your actual country and region or province so we can tailor "
            "the advice to your local conditions."
        )
    elif kind == "uninhabitable":
        headline = f'Crops cannot realistically grow at "{loc}".'
        detail = (
            "That environment cannot support normal crop growing. Please enter "
            "the country and region or province where your farm is located."
        )
    else:
        headline = f'Plants cannot grow at "{loc}".'
        detail = (
            "Please enter a real place on Earth where your farm is located — "
            "your country and region or province."
        )

    message = f"## Location Not Accepted\n\n**{headline}**\n\n{detail}"
    if reason:
        message += f"\n\n*{reason}*"
    return {"ok": False, "message": message}


def _parse_json_object(text):
    """Extract the first JSON object from a model reply, tolerant of stray
    markdown fences or surrounding prose."""
    if not text:
        return None
    text = text.strip()
    # Strip ```json ... ``` fences if present.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except (ValueError, TypeError):
        return None


@app.route("/", methods=["OPTIONS"])
def options():
    return Response(status=200, headers=CORS_HEADERS)


@app.route("/", methods=["POST"])
def diagnose():
    data = request.get_json(silent=True) or {}
    file_data = data.get("file_data")
    file_mime = data.get("file_mime")
    crop_name = data.get("crop_name", "")
    location = data.get("location", "")

    # --- Location gate ----------------------------------------------------
    # Reject places off Earth or where crops cannot grow.
    loc_verdict = validate_location(location)
    if not loc_verdict.get("ok"):
        loc_message = loc_verdict["message"]

        def loc_rejected():
            yield loc_message

        return Response(
            stream_with_context(loc_rejected()),
            content_type="text/plain; charset=utf-8",
            headers=CORS_HEADERS,
        )

    # --- Image gate -------------------------------------------------------
    # The photo is optional. If none is provided, proceed straight to a
    # text-only diagnosis. If an image is present, validate it first.
    if file_data and file_mime and file_mime.startswith("image/"):
        verdict = validate_image(file_data, file_mime, crop_name)
        if not verdict.get("ok"):
            reject_message = verdict["message"]

            def rejected():
                yield reject_message

            return Response(
                stream_with_context(rejected()),
                content_type="text/plain; charset=utf-8",
                headers=CORS_HEADERS,
            )

    # --- Passed the gate: stream the full diagnosis -----------------------
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
