/* ==========================================================================
   AgroShield AI — frontend logic
   - Collects the 10 widget inputs
   - Reads the uploaded photo as base64 (strips the data: prefix)
   - Streams the diagnosis from the Lambda Function URL token-by-token
   - Renders each complete line as animated, markdown-formatted spans
   ========================================================================== */

// Injected by GitHub Actions via sed. Leave the token exactly as-is.
const DIAGNOSIS_URL = "__DIAGNOSIS_FUNCTION_URL__";

// --------------------------------------------------------------------------
// State for the uploaded photo (raw base64 + MIME type)
// --------------------------------------------------------------------------
let fileData = null; // raw base64 string, no "data:...;base64," prefix
let fileMime = null; // e.g. "image/png"

// --------------------------------------------------------------------------
// Slider live values
// --------------------------------------------------------------------------
const cropAge = document.getElementById("crop_age");
const cropAgeOut = document.getElementById("crop_age_out");
cropAge.addEventListener("input", () => {
  cropAgeOut.textContent = cropAge.value;
});

const fieldPct = document.getElementById("field_percentage");
const fieldPctOut = document.getElementById("field_percentage_out");
fieldPct.addEventListener("input", () => {
  fieldPctOut.textContent = fieldPct.value + "%";
});

// --------------------------------------------------------------------------
// File upload: drag & drop + click, FileReader.readAsDataURL, strip prefix
// --------------------------------------------------------------------------
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("crop_photo");
const dropzoneInner = document.getElementById("dropzoneInner");
const dropzonePreview = document.getElementById("dropzonePreview");
const previewImg = document.getElementById("previewImg");
const previewName = document.getElementById("previewName");
const removePhoto = document.getElementById("removePhoto");

dropzone.addEventListener("click", (e) => {
  if (e.target === removePhoto) return;
  fileInput.click();
});
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});

["dragenter", "dragover"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  })
);
dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files && e.dataTransfer.files[0];
  if (file) handleFile(file);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files && fileInput.files[0]) handleFile(fileInput.files[0]);
});
removePhoto.addEventListener("click", clearFile);

function handleFile(file) {
  if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
    alert("Please upload a JPG, PNG, or WEBP image.");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    const result = reader.result; // "data:<mime>;base64,<data>"
    const comma = result.indexOf(",");
    fileData = result.slice(comma + 1); // strip the "data:...;base64," prefix
    fileMime = file.type;

    previewImg.src = result;
    previewName.textContent = file.name;
    dropzoneInner.hidden = true;
    dropzonePreview.hidden = false;
  };
  reader.readAsDataURL(file);
}

function clearFile() {
  fileData = null;
  fileMime = null;
  fileInput.value = "";
  previewImg.src = "";
  previewName.textContent = "";
  dropzoneInner.hidden = false;
  dropzonePreview.hidden = true;
}

// --------------------------------------------------------------------------
// Markdown line rendering (per-line, as spec'd)
// Supports: #/##/### headers, **bold**, *italic*, `code`, bullets (- or *),
// numbered lists, --- horizontal rule.
// --------------------------------------------------------------------------
function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderInline(text) {
  let t = escapeHtml(text);
  t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  return t;
}

function makeLineSpan(rawLine) {
  const span = document.createElement("span");
  span.className = "md-line";
  const line = rawLine.replace(/\s+$/, "");

  if (line.trim() === "---") {
    span.classList.add("hr");
    return span;
  }
  if (/^###\s+/.test(line)) {
    span.classList.add("h3");
    span.innerHTML = renderInline(line.replace(/^###\s+/, ""));
    return span;
  }
  if (/^##\s+/.test(line)) {
    span.classList.add("h2");
    span.innerHTML = renderInline(line.replace(/^##\s+/, ""));
    return span;
  }
  if (/^#\s+/.test(line)) {
    span.classList.add("h1");
    span.innerHTML = renderInline(line.replace(/^#\s+/, ""));
    return span;
  }
  if (/^\s*[-*]\s+/.test(line)) {
    span.classList.add("bullet");
    span.innerHTML = renderInline(line.replace(/^\s*[-*]\s+/, ""));
    return span;
  }
  if (/^\s*\d+\.\s+/.test(line)) {
    span.classList.add("numbered");
    span.innerHTML = renderInline(line);
    return span;
  }
  span.innerHTML = renderInline(line) || "&nbsp;";
  return span;
}

// --------------------------------------------------------------------------
// Panel helpers
// --------------------------------------------------------------------------
const panelStatus = document.getElementById("panelStatus");
const output = document.getElementById("diagnosisOutput");
const runBtn = document.getElementById("runAll");

function showSpinner() {
  output.classList.remove("active");
  output.innerHTML = "";
  panelStatus.innerHTML =
    '<div class="spinner-wrap"><div class="spinner"></div>' +
    "<span>Analysing your crop… growing your diagnosis 🌱</span></div>";
}

function showError(message) {
  output.classList.remove("active");
  panelStatus.innerHTML =
    '<div class="error-box"><span class="error-icon">⚠️</span>' +
    "<span>Sorry, something went wrong.</span>" +
    '<span style="font-weight:600;font-size:13px;">' +
    escapeHtml(message) +
    "</span></div>";
}

function beginOutput() {
  panelStatus.innerHTML = "";
  output.innerHTML = "";
  output.classList.add("active");
}

// --------------------------------------------------------------------------
// Collect the form values into the POST body
// --------------------------------------------------------------------------
function collectBody() {
  const body = {
    crop_name: document.getElementById("crop_name").value,
    crop_age: cropAge.value,
    plant_part: document.getElementById("plant_part").value,
    symptoms: document.getElementById("symptoms").value,
    field_percentage: fieldPct.value,
    weather: document.getElementById("weather").value,
    pests: document.getElementById("pests").value,
    treatments: document.getElementById("treatments").value,
    location: document.getElementById("location").value,
  };
  // Only include file_data if a photo was selected.
  if (fileData && fileMime) {
    body.file_data = fileData;
    body.file_mime = fileMime;
  }
  return body;
}

function validate() {
  const required = [
    ["crop_name", "Crop Name and Variety"],
    ["plant_part", "Plant Part Affected"],
    ["symptoms", "Symptom Description"],
    ["weather", "Recent Weather Conditions"],
    ["location", "Farm Location"],
  ];
  for (const [id, label] of required) {
    if (!document.getElementById(id).value.trim()) {
      alert("Please fill in: " + label);
      document.getElementById(id).focus();
      return false;
    }
  }
  return true;
}

// --------------------------------------------------------------------------
// Streaming: fetch + response.body.getReader(), buffer incomplete lines,
// flush complete lines as animated markdown spans, blinking cursor on active.
// --------------------------------------------------------------------------
async function runDiagnosis() {
  if (!validate()) return;

  if (!DIAGNOSIS_URL || DIAGNOSIS_URL.indexOf("__") === 0) {
    showError(
      "The diagnosis service URL has not been configured yet. Deploy via " +
        "GitHub Actions so the Function URL is injected."
    );
    return;
  }

  runBtn.disabled = true;
  showSpinner();

  try {
    const response = await fetch(DIAGNOSIS_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectBody()),
    });

    if (!response.ok || !response.body) {
      throw new Error("HTTP " + response.status);
    }

    beginOutput();

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let activeLine = null; // span currently receiving tokens (blinking cursor)

    function ensureActiveLine() {
      if (!activeLine) {
        activeLine = document.createElement("span");
        activeLine.className = "md-line cursor";
        activeLine.textContent = "";
        output.appendChild(activeLine);
      }
    }

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      let newlineIndex;
      while ((newlineIndex = buffer.indexOf("\n")) !== -1) {
        const rawLine = buffer.slice(0, newlineIndex);
        buffer = buffer.slice(newlineIndex + 1);

        // finalise this line as a rendered markdown span
        if (activeLine) activeLine.remove();
        activeLine = null;
        const span = makeLineSpan(rawLine);
        output.appendChild(span);
        output.scrollTop = output.scrollHeight;
      }

      // show the in-progress remainder on a blinking active line
      if (buffer.length) {
        ensureActiveLine();
        activeLine.textContent = buffer;
        output.scrollTop = output.scrollHeight;
      }
    }

    // flush any trailing text once the stream ends
    if (activeLine) activeLine.remove();
    if (buffer.length) {
      output.appendChild(makeLineSpan(buffer));
    }
    if (!output.childNodes.length) {
      output.appendChild(makeLineSpan("_No diagnosis was returned. Please try again._"));
    }
    output.scrollTop = output.scrollHeight;
  } catch (err) {
    showError(err && err.message ? err.message : String(err));
  } finally {
    runBtn.disabled = false;
  }
}

// "Run All" button fires the AI call.
runBtn.addEventListener("click", runDiagnosis);
