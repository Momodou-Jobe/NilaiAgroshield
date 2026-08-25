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


# Bilingual templates for the gate rejection messages. {crop}/{seen}/{loc}
# are filled in at runtime. "ms" = Bahasa Melayu.
GATE_TEXT = {
    "en": {
        "photo_title": "Photo Not Accepted",
        "not_plant_h": "That photo does not look like a plant.",
        "not_plant_d": (
            "Please upload a clear photo of the affected plant part — for "
            "example a leaf, stem, root, flower, or fruit."
        ),
        "blurry_h": "That photo is not clear enough to analyse.",
        "blurry_d": (
            "Please take another photo that is sharp and well-lit. Get closer "
            "to the affected area, hold the camera steady, and avoid shadows, "
            "glare, or blur."
        ),
        "mismatch_h": 'That photo does not match "{crop}".{seen}',
        "mismatch_seen": " It looks more like {detected}.",
        "mismatch_d": (
            'Please upload a photo of your {crop} plant part (leaf, stem, '
            "root, flower, or fruit) so the diagnosis stays accurate."
        ),
        "loc_title": "Location Not Accepted",
        "vague_h": '"{loc}" is not specific enough.',
        "vague_d": (
            "Please enter an actual place instead of a general phrase like "
            '"here", "there", or "my village". Type your country and region '
            'or province — for example "Kenya - Rift Valley", '
            '"India - Punjab", or "Nigeria - Kaduna".'
        ),
        "offearth_h": 'Plants cannot grow at "{loc}".',
        "offearth_d": (
            "That location is not on Earth. Crops need soil, air, water, and "
            "sunlight found only here on Earth. Please enter a real place on "
            "Earth — your country and region or province."
        ),
        "fictional_h": '"{loc}" does not appear to be a real place.',
        "fictional_d": (
            "We could not recognise that as a real location on Earth. Please "
            "enter your actual country and region or province."
        ),
        "uninhabitable_h": 'Crops cannot realistically grow at "{loc}".',
        "uninhabitable_d": (
            "That environment cannot support normal crop growing. Please enter "
            "the country and region or province where your farm is located."
        ),
    },
    "ms": {
        "photo_title": "Foto Tidak Diterima",
        "not_plant_h": "Foto itu tidak kelihatan seperti tumbuhan.",
        "not_plant_d": (
            "Sila muat naik foto yang jelas bagi bahagian tumbuhan yang "
            "terjejas — contohnya daun, batang, akar, bunga, atau buah."
        ),
        "blurry_h": "Foto itu tidak cukup jelas untuk dianalisis.",
        "blurry_d": (
            "Sila ambil foto lain yang tajam dan mempunyai pencahayaan yang "
            "baik. Dekatkan kamera ke bahagian terjejas, pegang kamera dengan "
            "stabil, dan elakkan bayang, silau, atau kekaburan."
        ),
        "mismatch_h": 'Foto itu tidak sepadan dengan "{crop}".{seen}',
        "mismatch_seen": " Ia lebih kelihatan seperti {detected}.",
        "mismatch_d": (
            "Sila muat naik foto bahagian tumbuhan {crop} anda (daun, batang, "
            "akar, bunga, atau buah) supaya diagnosis kekal tepat."
        ),
        "loc_title": "Lokasi Tidak Diterima",
        "vague_h": '"{loc}" tidak cukup khusus.',
        "vague_d": (
            "Sila masukkan tempat sebenar dan bukan frasa umum seperti "
            '"di sini", "di sana", atau "kampung saya". Taipkan negara dan '
            'wilayah atau negeri anda — contohnya "Selangor - Sabak Bernam", '
            '"Kedah - Kota Setar", atau "Sarawak - Miri".'
        ),
        "offearth_h": 'Tumbuhan tidak boleh tumbuh di "{loc}".',
        "offearth_d": (
            "Lokasi itu bukan di Bumi. Tanaman memerlukan tanah, udara, air, "
            "dan cahaya matahari yang hanya terdapat di Bumi. Sila masukkan "
            "tempat sebenar di Bumi — negara dan wilayah atau negeri anda."
        ),
        "fictional_h": '"{loc}" tidak kelihatan seperti tempat sebenar.',
        "fictional_d": (
            "Kami tidak dapat mengenali itu sebagai lokasi sebenar di Bumi. "
            "Sila masukkan negara dan wilayah atau negeri anda yang sebenar."
        ),
        "uninhabitable_h": 'Tanaman tidak boleh tumbuh secara realistik di "{loc}".',
        "uninhabitable_d": (
            "Persekitaran itu tidak dapat menyokong penanaman tanaman biasa. "
            "Sila masukkan negara dan wilayah atau negeri di mana ladang anda "
            "terletak."
        ),
    },
}


def gate_lang(language):
    """Map the incoming language label to a GATE_TEXT key."""
    if (language or "").strip().lower().startswith("bahasa"):
        return "ms"
    return "en"


def validate_image(file_data, file_mime, crop_name, language="English"):
    """Run a quick, non-streaming gate over the uploaded photo.

    Returns a dict:
      {"ok": True}                          -> photo passed, proceed to diagnose
      {"ok": False, "message": "<text>"}    -> photo rejected, show message
    On any unexpected error we fail open (allow diagnosis) so a validation
    hiccup never blocks a legitimate farmer.
    """
    lang = gate_lang(language)
    txt = GATE_TEXT[lang]
    crop = crop_name.strip() or "the crop the farmer named"
    instruction = (
        f'The farmer says this photo is of: "{crop}". '
        f'Write the "reason" field in {language}. '
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

    # Build a friendly, specific rejection message from the localized templates.
    if not is_plant:
        headline = txt["not_plant_h"]
        detail = txt["not_plant_d"]
    elif not is_clear:
        headline = txt["blurry_h"]
        detail = txt["blurry_d"]
    else:  # not matches
        if detected and detected.lower() != "unknown":
            seen = txt["mismatch_seen"].format(detected=detected)
        else:
            seen = ""
        headline = txt["mismatch_h"].format(crop=crop, seen=seen)
        detail = txt["mismatch_d"].format(crop=crop)

    message = f'## {txt["photo_title"]}\n\n**{headline}**\n\n{detail}'
    if reason:
        message += f"\n\n*{reason}*"
    return {"ok": False, "message": message}


def validate_location(location, language="English"):
    """Check whether the farm location is a real place on Earth where crops
    can grow.

    Returns a dict:
      {"ok": True}                          -> location fine, proceed
      {"ok": False, "message": "<text>"}    -> location rejected, show message
    Fails open (allows diagnosis) on any unexpected error or blank input so a
    validation hiccup never blocks a legitimate farmer.
    """
    lang = gate_lang(language)
    txt = GATE_TEXT[lang]
    loc = (location or "").strip()
    if not loc:
        # Location is required by the form; if empty, let the normal flow run.
        return {"ok": True}

    instruction = (
        f'The farmer entered this farm location: "{loc}". '
        f'Write the "reason" field in {language}. '
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
        headline = txt["vague_h"].format(loc=loc)
        detail = txt["vague_d"]
        message = f'## {txt["loc_title"]}\n\n**{headline}**\n\n{detail}'
        if reason:
            message += f"\n\n*{reason}*"
        return {"ok": False, "message": message}

    if kind == "off_earth":
        headline = txt["offearth_h"].format(loc=loc)
        detail = txt["offearth_d"]
    elif kind == "fictional":
        headline = txt["fictional_h"].format(loc=loc)
        detail = txt["fictional_d"]
    elif kind == "uninhabitable":
        headline = txt["uninhabitable_h"].format(loc=loc)
        detail = txt["uninhabitable_d"]
    else:
        headline = txt["offearth_h"].format(loc=loc)
        detail = txt["offearth_d"]

    message = f'## {txt["loc_title"]}\n\n**{headline}**\n\n{detail}'
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
    language = (data.get("language") or "English").strip() or "English"

    # --- Location gate ----------------------------------------------------
    # Reject places off Earth or where crops cannot grow.
    loc_verdict = validate_location(location, language)
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
        verdict = validate_image(file_data, file_mime, crop_name, language)
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

    # Respond in the language the farmer chose in the UI.
    system_prompt = (
        SYSTEM_PROMPT
        + f"\n\nIMPORTANT: Write your entire response in {language}. "
        "Keep the markdown section headings, but translate their text into "
        f"{language} as well. Use simple, everyday {language}."
    )

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "temperature": 0.4,
        "system": system_prompt,
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


# ---------------------------------------------------------------------------
# Translation endpoint: converts already-generated text between English and
# Bahasa Melayu without re-running a diagnosis. Streams the result back in the
# same token-by-token style the frontend already renders.
# ---------------------------------------------------------------------------
TRANSLATE_SYSTEM_PROMPT = (
    "You are a professional translator for a farming app. Translate the text "
    "the user sends into the requested target language. Rules:\n"
    "- Preserve the meaning exactly; do not add, remove, or explain anything.\n"
    "- Keep all markdown formatting intact: headings (#, ##, ###), bold "
    "(**text**), italics, bullet points, numbered lists, and line breaks.\n"
    "- Translate the text of headings too, but keep the heading markers.\n"
    "- Keep product names, chemical names, numbers, and units as-is.\n"
    "- Use simple, everyday language a smallholder farmer can understand.\n"
    "- Output ONLY the translated text, with no preamble or quotes."
)


@app.route("/translate", methods=["OPTIONS"])
def translate_options():
    return Response(status=200, headers=CORS_HEADERS)


@app.route("/translate", methods=["POST"])
def translate():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    target = (data.get("target") or "English").strip() or "English"

    if not text:
        def empty():
            yield ""

        return Response(
            stream_with_context(empty()),
            content_type="text/plain; charset=utf-8",
            headers=CORS_HEADERS,
        )

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "temperature": 0,
        "system": TRANSLATE_SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Translate the following text into {target}. "
                            "Return only the translation.\n\n"
                            f"{text}"
                        ),
                    }
                ],
            }
        ],
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
                    piece = delta.get("text")
                    if piece:
                        yield piece
        except Exception as exc:  # noqa: BLE001 - surface any error to the client
            yield f"\n\n[Error translating: {exc}]"

    return Response(
        stream_with_context(generate()),
        content_type="text/plain; charset=utf-8",
        headers=CORS_HEADERS,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
