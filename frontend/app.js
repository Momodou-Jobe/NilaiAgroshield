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
// Internationalisation (English <-> Bahasa Melayu)
// --------------------------------------------------------------------------
const I18N = {
  en: {
    _langName: "English",
    _otherLangName: "Bahasa Melayu",
    tagline: "Crop Disease & Pest Diagnostic Tool",
    badge: "Your intelligent farming companion",
    welcome_title: "Welcome to AgroShield AI 🌱",
    welcome_body:
      "This app helps smallholder farmers quickly diagnose crop diseases and pest problems, get tailored treatment recommendations, and learn preventive farming practices. Fill in the details about your crop and its symptoms below, and our AI agricultural assistant will provide a thorough diagnosis and actionable advice.",
    form_title: "Tell us about your crop",
    w1_label: "1. Crop Name and Variety",
    w1_ph:
      "e.g., Maize - hybrid DK8031, Tomato - Roma variety, Rice - IR64. Enter your crop name and variety if known.",
    w2_label: "2. Crop Age in Weeks",
    w2_hint: "Slide to set how old the crop is (1–52 weeks)",
    w3_label: "3. Plant Part Affected",
    w3_placeholder: "Select the affected plant part",
    w3_leaves: "Leaves",
    w3_stem: "Stem",
    w3_roots: "Roots",
    w3_flowers: "Flowers",
    w3_fruits: "Fruits",
    w3_entire: "Entire plant",
    w3_multiple: "Multiple parts",
    w4_label: "4. Symptom Description",
    w4_ph:
      "Describe what you see in detail — e.g., yellow spots on leaves, brown lesions on stem, wilting despite watering, holes in leaves, white powder on surface, rotting roots, unusual discoloration, etc.",
    w5_label: "5. Field Affected Percentage",
    w5_hint: "Estimate how much of the field is affected (1–100%)",
    w6_label: "6. Recent Weather Conditions",
    w6_placeholder: "Select recent weather",
    w6_hot: "Hot and Dry",
    w6_humid: "Warm and Humid",
    w6_rainy: "Rainy and Wet",
    w6_mild: "Mild and Cloudy",
    w6_cold: "Cold",
    w6_mixed: "Mixed or Variable",
    w7_label: "7. Pest or Insect Observations",
    w7_ph:
      "Did you notice any insects, worms, flies, or other creatures on or near your crops? Describe their appearance, color, size, and behavior if possible. Leave blank if none observed.",
    w8_label: "8. Recent Treatments Applied",
    w8_ph:
      "Have you recently applied any fertilizers, pesticides, herbicides, or other treatments? If yes, mention the product name, quantity, and when it was applied. Leave blank if none.",
    w9_label: "9. Farm Location",
    w9_ph:
      "e.g., Kenya - Rift Valley region, India - Punjab state, Nigeria - Kaduna. Enter your country and region or province to help tailor advice to your local conditions.",
    w9_hint:
      'Enter an actual named place (country and region or province). General phrases like "here", "there", or "my village" cannot be used.',
    w10_label: "10. Crop Photo Upload",
    w10_hint:
      "Optional, but recommended for a more accurate diagnosis. If you upload a photo, it must be the same crop you named above — for example, if your crop is Maize, upload a photo of a maize leaf, stem, root, or fruit, not a different plant. Make sure the image is sharp and well-lit and shows the symptoms clearly. If the photo is not a plant, is too blurry, or does not match your crop, the app will ask you to upload a better one. Accepted formats: JPG, PNG, WEBP.",
    optional: "(optional)",
    dz_main: "Drag & drop your crop photo here",
    dz_sub: "or click to browse (JPG, PNG, WEBP)",
    remove: "Remove",
    run_btn: "Run Diagnosis",
    output_title: "AgroShield Diagnosis and Recommendations",
    empty_state:
      "Fill in the form and press Run Diagnosis. Your personalised diagnosis and treatment plan will stream in here.",
    team_title: "Meet the AgroShield Agronomy Team 🌍",
    team_1: "Amara Okafor — Lead Agronomist",
    team_2: "Daniel Mwangi — Plant Pathologist",
    team_3: "Priya Sharma — Soil & Crop Scientist",
    team_4: "Carlos Mendes — Pest Management Specialist",
    disclaimer:
      "AgroShield AI provides guidance to support your decisions. Always confirm treatments with a local agricultural extension officer before applying chemicals. 🌱",
    // runtime strings
    spinner: "Analysing your crop… growing your diagnosis 🌱",
    translating: "Translating… 🌐",
    err_generic: "Sorry, something went wrong.",
    err_no_url:
      "The diagnosis service URL has not been configured yet. Deploy via GitHub Actions so the Function URL is injected.",
    no_diagnosis: "_No diagnosis was returned. Please try again._",
    fill_field: "Please fill in: ",
  },
  ms: {
    _langName: "Bahasa Melayu",
    _otherLangName: "English",
    tagline: "Alat Diagnostik Penyakit & Perosak Tanaman",
    badge: "Rakan pertanian pintar anda",
    welcome_title: "Selamat datang ke AgroShield AI 🌱",
    welcome_body:
      "Aplikasi ini membantu petani kecil mendiagnosis penyakit tanaman dan masalah perosak dengan cepat, mendapatkan cadangan rawatan yang sesuai, dan mempelajari amalan pertanian pencegahan. Isikan maklumat tentang tanaman anda dan gejalanya di bawah, dan pembantu pertanian AI kami akan memberikan diagnosis menyeluruh serta nasihat yang boleh dilaksanakan.",
    form_title: "Beritahu kami tentang tanaman anda",
    w1_label: "1. Nama dan Jenis Tanaman",
    w1_ph:
      "cth., Jagung - hibrid DK8031, Tomato - jenis Roma, Padi - IR64. Masukkan nama dan jenis tanaman anda jika diketahui.",
    w2_label: "2. Usia Tanaman (Minggu)",
    w2_hint: "Luncurkan untuk menetapkan usia tanaman (1–52 minggu)",
    w3_label: "3. Bahagian Tumbuhan Terjejas",
    w3_placeholder: "Pilih bahagian tumbuhan yang terjejas",
    w3_leaves: "Daun",
    w3_stem: "Batang",
    w3_roots: "Akar",
    w3_flowers: "Bunga",
    w3_fruits: "Buah",
    w3_entire: "Seluruh tumbuhan",
    w3_multiple: "Beberapa bahagian",
    w4_label: "4. Penerangan Gejala",
    w4_ph:
      "Terangkan apa yang anda lihat secara terperinci — cth., bintik kuning pada daun, lesi perang pada batang, layu walaupun disiram, lubang pada daun, serbuk putih pada permukaan, akar reput, perubahan warna luar biasa, dsb.",
    w5_label: "5. Peratusan Ladang Terjejas",
    w5_hint: "Anggarkan berapa banyak ladang yang terjejas (1–100%)",
    w6_label: "6. Keadaan Cuaca Terkini",
    w6_placeholder: "Pilih cuaca terkini",
    w6_hot: "Panas dan Kering",
    w6_humid: "Hangat dan Lembap",
    w6_rainy: "Hujan dan Basah",
    w6_mild: "Sederhana dan Mendung",
    w6_cold: "Sejuk",
    w6_mixed: "Bercampur atau Berubah-ubah",
    w7_label: "7. Pemerhatian Perosak atau Serangga",
    w7_ph:
      "Adakah anda perasan sebarang serangga, ulat, lalat, atau makhluk lain pada atau berhampiran tanaman anda? Terangkan rupa, warna, saiz, dan tingkah lakunya jika boleh. Biarkan kosong jika tiada.",
    w8_label: "8. Rawatan Terkini Digunakan",
    w8_ph:
      "Adakah anda baru-baru ini menggunakan sebarang baja, racun perosak, racun rumpai, atau rawatan lain? Jika ya, nyatakan nama produk, kuantiti, dan bila ia digunakan. Biarkan kosong jika tiada.",
    w9_label: "9. Lokasi Ladang",
    w9_ph:
      "cth., Selangor - Sabak Bernam, Kedah - Kota Setar, Sarawak - Miri. Masukkan negara dan wilayah atau negeri anda untuk membantu menyesuaikan nasihat dengan keadaan tempatan anda.",
    w9_hint:
      'Masukkan nama tempat sebenar (negara dan wilayah atau negeri). Frasa umum seperti "di sini", "di sana", atau "kampung saya" tidak boleh digunakan.',
    w10_label: "10. Muat Naik Foto Tanaman",
    w10_hint:
      "Pilihan, tetapi disyorkan untuk diagnosis yang lebih tepat. Jika anda memuat naik foto, ia mesti tanaman yang sama seperti yang anda namakan di atas — contohnya, jika tanaman anda ialah Jagung, muat naik foto daun, batang, akar, atau buah jagung, bukan tumbuhan lain. Pastikan imej jelas dan mempunyai pencahayaan yang baik serta menunjukkan gejala dengan jelas. Jika foto bukan tumbuhan, terlalu kabur, atau tidak sepadan dengan tanaman anda, aplikasi akan meminta anda memuat naik yang lebih baik. Format diterima: JPG, PNG, WEBP.",
    optional: "(pilihan)",
    dz_main: "Seret & lepas foto tanaman anda di sini",
    dz_sub: "atau klik untuk melayari (JPG, PNG, WEBP)",
    remove: "Buang",
    run_btn: "Jalankan Diagnosis",
    output_title: "Diagnosis dan Cadangan AgroShield",
    empty_state:
      "Isikan borang dan tekan Jalankan Diagnosis. Diagnosis peribadi dan pelan rawatan anda akan dipaparkan di sini.",
    team_title: "Kenali Pasukan Agronomi AgroShield 🌍",
    team_1: "Amara Okafor — Ketua Agronomis",
    team_2: "Daniel Mwangi — Pakar Patologi Tumbuhan",
    team_3: "Priya Sharma — Saintis Tanah & Tanaman",
    team_4: "Carlos Mendes — Pakar Pengurusan Perosak",
    disclaimer:
      "AgroShield AI memberikan panduan untuk menyokong keputusan anda. Sentiasa sahkan rawatan dengan pegawai pengembangan pertanian tempatan sebelum menggunakan bahan kimia. 🌱",
    spinner: "Menganalisis tanaman anda… menyediakan diagnosis 🌱",
    translating: "Menterjemah… 🌐",
    err_generic: "Maaf, sesuatu telah berlaku.",
    err_no_url:
      "URL perkhidmatan diagnosis belum dikonfigurasikan. Sebarkan melalui GitHub Actions supaya Function URL dimasukkan.",
    no_diagnosis: "_Tiada diagnosis dikembalikan. Sila cuba lagi._",
    fill_field: "Sila isikan: ",
  },
};

// Current language: restore from localStorage, default English.
let currentLang = localStorage.getItem("agroshield_lang") || "en";

function t(key) {
  const pack = I18N[currentLang] || I18N.en;
  return pack[key] != null ? pack[key] : I18N.en[key] || "";
}

function applyLanguage(lang) {
  currentLang = I18N[lang] ? lang : "en";
  localStorage.setItem("agroshield_lang", currentLang);
  document.documentElement.lang = currentLang === "ms" ? "ms" : "en";

  // Text content
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    const val = t(key);
    if (val) el.textContent = val;
  });
  // Placeholders
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
    const key = el.getAttribute("data-i18n-ph");
    const val = t(key);
    if (val) el.setAttribute("placeholder", val);
  });
  // Toggle button shows the language you can switch TO.
  const label = document.getElementById("langToggleLabel");
  if (label) label.textContent = t("_otherLangName");
}

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
    "<span>" +
    escapeHtml(t("spinner")) +
    "</span></div>";
}

function showError(message) {
  output.classList.remove("active");
  panelStatus.innerHTML =
    '<div class="error-box"><span class="error-icon">⚠️</span>' +
    "<span>" +
    escapeHtml(t("err_generic")) +
    "</span>" +
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
  // Tell the backend which language to answer in.
  body.language = currentLang === "ms" ? "Bahasa Melayu" : "English";
  // Only include file_data if a photo was selected.
  if (fileData && fileMime) {
    body.file_data = fileData;
    body.file_mime = fileMime;
  }
  return body;
}

function validate() {
  const required = [
    ["crop_name", "w1_label"],
    ["plant_part", "w3_label"],
    ["symptoms", "w4_label"],
    ["weather", "w6_label"],
    ["location", "w9_label"],
  ];
  for (const [id, key] of required) {
    if (!document.getElementById(id).value.trim()) {
      alert(t("fill_field") + t(key));
      document.getElementById(id).focus();
      return false;
    }
  }
  // The crop photo is optional. If one is provided, the backend still checks
  // that it is a real, clear plant part matching the named crop.
  return true;
}

// Raw markdown of the last diagnosis (or gate message) shown on screen, and
// the language it is currently displayed in. Used to re-translate on toggle.
let lastOutputText = "";
let lastOutputLang = currentLang;

// Render a full markdown string into the output panel, line by line.
function renderMarkdownToOutput(text) {
  beginOutput();
  const lines = String(text).split("\n");
  for (const line of lines) {
    output.appendChild(makeLineSpan(line));
  }
  output.scrollTop = 0;
}

// --------------------------------------------------------------------------
// Streaming: fetch + response.body.getReader(), buffer incomplete lines,
// flush complete lines as animated markdown spans, blinking cursor on active.
// --------------------------------------------------------------------------
async function runDiagnosis() {
  if (!validate()) return;

  if (!DIAGNOSIS_URL || DIAGNOSIS_URL.indexOf("__") === 0) {
    showError(t("err_no_url"));
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
    let accumulated = ""; // full raw markdown, for later re-translation
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

      const decoded = decoder.decode(value, { stream: true });
      buffer += decoded;
      accumulated += decoded;

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
      output.appendChild(makeLineSpan(t("no_diagnosis")));
    }
    output.scrollTop = output.scrollHeight;

    // Remember the result so the language toggle can translate it in place.
    lastOutputText = accumulated;
    lastOutputLang = currentLang;
  } catch (err) {
    showError(err && err.message ? err.message : String(err));
  } finally {
    runBtn.disabled = false;
  }
}

// "Run All" button fires the AI call.
runBtn.addEventListener("click", runDiagnosis);

// --------------------------------------------------------------------------
// Translation helper: POST text to the /translate endpoint and return the full
// translated string (reads the streamed response to completion).
// --------------------------------------------------------------------------
const TRANSLATE_URL =
  DIAGNOSIS_URL && DIAGNOSIS_URL.indexOf("__") !== 0
    ? DIAGNOSIS_URL.replace(/\/+$/, "") + "/translate"
    : "";

async function translateText(text, targetLabel) {
  if (!text || !TRANSLATE_URL) return text;
  const response = await fetch(TRANSLATE_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: text, target: targetLabel }),
  });
  if (!response.ok || !response.body) {
    throw new Error("HTTP " + response.status);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let out = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    out += decoder.decode(value, { stream: true });
  }
  return out.trim();
}

// The free-text input fields whose typed content we also translate.
const TEXT_INPUT_IDS = [
  "crop_name",
  "symptoms",
  "pests",
  "treatments",
  "location",
];

async function translateInputs(targetLabel) {
  const jobs = [];
  for (const id of TEXT_INPUT_IDS) {
    const el = document.getElementById(id);
    const value = el.value.trim();
    if (value) {
      jobs.push(
        translateText(value, targetLabel)
          .then((translated) => {
            if (translated) el.value = translated;
          })
          .catch(() => {
            /* leave the original text if translation fails */
          })
      );
    }
  }
  await Promise.all(jobs);
}

// --------------------------------------------------------------------------
// Language toggle (English <-> Bahasa Melayu)
//   1. switches all static UI text
//   2. translates the typed inputs into the new language
//   3. translates the diagnosis already on screen into the new language
// --------------------------------------------------------------------------
const langToggle = document.getElementById("langToggle");
let switching = false;

langToggle.addEventListener("click", async () => {
  if (switching) return;
  const newLang = currentLang === "en" ? "ms" : "en";
  const targetLabel = newLang === "ms" ? "Bahasa Melayu" : "English";

  // Always switch the static UI immediately.
  applyLanguage(newLang);

  const hasOutput = lastOutputText && lastOutputText.trim().length > 0;
  const hasInputs = TEXT_INPUT_IDS.some(
    (id) => document.getElementById(id).value.trim().length > 0
  );

  // Nothing typed or generated yet -> just the UI switch.
  if ((!hasOutput && !hasInputs) || !TRANSLATE_URL) return;

  switching = true;
  langToggle.disabled = true;

  // Show a translating state over any existing output.
  if (hasOutput) {
    output.classList.remove("active");
    panelStatus.innerHTML =
      '<div class="spinner-wrap"><div class="spinner"></div>' +
      "<span>" +
      escapeHtml(t("translating")) +
      "</span></div>";
  }

  try {
    // Translate inputs and output in parallel.
    const tasks = [translateInputs(targetLabel)];
    if (hasOutput) {
      tasks.push(
        translateText(lastOutputText, targetLabel).then((translated) => {
          if (translated) {
            lastOutputText = translated;
            lastOutputLang = newLang;
            renderMarkdownToOutput(translated);
          }
        })
      );
    }
    await Promise.all(tasks);
  } catch (err) {
    if (hasOutput) showError(err && err.message ? err.message : String(err));
  } finally {
    switching = false;
    langToggle.disabled = false;
  }
});

// Apply the saved/default language on first load.
applyLanguage(currentLang);
