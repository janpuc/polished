// The barcode scanner (DESIGN 7.3): camera into a full-screen <dialog>, decoded continuously with
// the vendored zxing-wasm (UPC-A, EAN-13 and EAN-8 only), plus a still-photo fallback and the
// typed field on the page. A code is handed to /lookup/resolve; the server normalises it.
//
// iPhone Safari has no BarcodeDetector, so zxing-wasm is the real path; the native detector is
// used for video frames only where a browser has it. The camera is stopped the moment a code is
// accepted, when the dialog closes (Esc, Close) and when the page is hidden.
const ZXING_URL = "/static/vendor/zxing-wasm/reader/index.js";
const WASM_URL = "/static/vendor/zxing-wasm/zxing_reader.wasm";
const FORMATS = ["EAN13", "UPCA", "EAN8"];
const READER_OPTIONS = {
  formats: FORMATS,
  tryHarder: true,
  tryRotate: true,
  tryInvert: false,
  maxNumberOfSymbols: 1,
};
const FRAME_MS = 160; // about 6 frames a second
const CONFIRM_READS = 2; // identical consecutive reads before a code is accepted
const HINT_AFTER_MS = 8000;
const STILL_MAX_SIDE = 2000;

const dialog = document.getElementById("scanner");
const video = document.getElementById("scanner-video");
const guide = dialog?.querySelector(".scanner-guide");
const status = document.getElementById("scanner-status");
const note = document.getElementById("scan-note");
const photoInput = document.getElementById("scan-photo");
const field = document.getElementById("lookup-q");
const STATUS_DEFAULT = status?.textContent ?? "";

let zxing = null;
let session = null;
let nativeDetector = null;
try {
  if ("BarcodeDetector" in window) {
    nativeDetector = new window.BarcodeDetector({ formats: ["ean_13", "upc_a", "ean_8"] });
  }
} catch {
  nativeDetector = null;
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function showNote(text) {
  if (!note) return;
  note.textContent = text;
  note.hidden = !text;
}

function loadDecoder() {
  zxing ??= import(ZXING_URL)
    .then(async (module) => {
      await module.prepareZXingModule({
        overrides: {
          locateFile: (path, prefix) => (path.endsWith(".wasm") ? WASM_URL : prefix + path),
        },
        fireImmediately: true,
      });
      return module;
    })
    .catch((error) => {
      zxing = null; // allow a retry
      throw error;
    });
  return zxing;
}

function showResult(code) {
  const url = `/lookup/resolve?q=${encodeURIComponent(code)}&via=scan`;
  if (field) field.value = "";
  showNote("");
  window.htmx.ajax("GET", url, "#lookup-result").then(() => {
    document.getElementById("lookup-result")?.scrollIntoView({ block: "start" });
  });
}

function cameraProblem() {
  if (navigator.mediaDevices?.getUserMedia) return "";
  if (!window.isSecureContext) {
    return (
      `The camera only works on a secure (https) page, and this one is ${location.origin}. ` +
      "Take a photo of the barcode instead, or type the digits."
    );
  }
  return "This browser can't open the camera. Take a photo of the barcode instead, or type the digits.";
}

function describeCameraError(error) {
  const advice = "Take a photo of the barcode instead, or type the digits.";
  switch (error?.name) {
    case "NotAllowedError":
    case "SecurityError":
      return `Camera access is blocked. Allow it in Settings › Safari › Camera (the home-screen app asks separately), then try again. ${advice}`;
    case "NotFoundError":
    case "OverconstrainedError":
      return `No camera was found. ${advice}`;
    case "NotReadableError":
    case "AbortError":
      return `The camera is busy in another app. Close it and try again. ${advice}`;
    default:
      return `The camera could not be started (${error?.name ?? "unknown error"}). ${advice}`;
  }
}

function stopCamera() {
  if (!session) return;
  session.active = false;
  clearTimeout(session.hint);
  for (const track of session.stream.getTracks()) track.stop();
  session = null;
}

function closeScanner() {
  stopCamera();
  if (dialog.open) dialog.close();
}

// The part of the video frame under the framing guide, in video pixels. The video fills the
// dialog with object-fit: cover, so the guide's box is mapped through that scaling.
function guideCrop() {
  const box = video.getBoundingClientRect();
  const frame = guide.getBoundingClientRect();
  const scale = Math.max(box.width / video.videoWidth, box.height / video.videoHeight);
  const hiddenX = (video.videoWidth * scale - box.width) / 2;
  const hiddenY = (video.videoHeight * scale - box.height) / 2;
  const x = Math.max(0, Math.round((frame.left - box.left + hiddenX) / scale));
  const y = Math.max(0, Math.round((frame.top - box.top + hiddenY) / scale));
  return {
    x,
    y,
    width: Math.min(video.videoWidth - x, Math.round(frame.width / scale)),
    height: Math.min(video.videoHeight - y, Math.round(frame.height / scale)),
  };
}

const canvas = document.createElement("canvas");
const canvasContext = canvas.getContext("2d", { willReadFrequently: true });

async function readFrame() {
  if (nativeDetector) {
    const found = await nativeDetector.detect(video);
    return found[0]?.rawValue ?? null;
  }
  const crop = guideCrop();
  canvas.width = crop.width;
  canvas.height = crop.height;
  canvasContext.drawImage(video, crop.x, crop.y, crop.width, crop.height, 0, 0, crop.width, crop.height);
  const results = await (await zxing).readBarcodes(
    canvasContext.getImageData(0, 0, crop.width, crop.height),
    READER_OPTIONS
  );
  return results.find((result) => result.isValid)?.text ?? null;
}

function accept(code) {
  stopCamera(); // the camera is off before anything else happens; the video keeps its last frame
  navigator.vibrate?.(60);
  dialog.classList.add("is-hit");
  status.textContent = "Got it";
  setTimeout(() => {
    dialog.close();
    showResult(code);
  }, 250);
}

async function scanLoop(current) {
  let previous = null;
  let reads = 0;
  while (current.active) {
    const started = performance.now();
    if (!video.videoWidth || video.readyState < 2) {
      await sleep(FRAME_MS);
      continue;
    }
    let code = null;
    try {
      code = await readFrame();
    } catch (error) {
      closeScanner();
      showNote(`The scanner stopped (${error?.message ?? error}). Take a photo of the barcode instead.`);
      return;
    }
    if (!current.active) return;
    reads = code && code === previous ? reads + 1 : code ? 1 : 0;
    previous = code;
    if (reads >= CONFIRM_READS) {
      accept(code);
      return;
    }
    await sleep(Math.max(0, FRAME_MS - (performance.now() - started)));
  }
}

async function openScanner() {
  if (session) return;
  const problem = cameraProblem();
  if (problem) {
    showNote(problem);
    return;
  }
  showNote("");
  // The decoder downloads while the camera permission prompt is up.
  const decoder = nativeDetector ? Promise.resolve() : loadDecoder();
  decoder.catch(() => {});
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } },
      audio: false,
    });
  } catch (error) {
    showNote(describeCameraError(error));
    return;
  }
  const current = { stream, active: true, hint: 0 };
  session = current;
  video.srcObject = stream;
  dialog.classList.remove("is-hit");
  status.textContent = STATUS_DEFAULT;
  dialog.showModal();
  video.play().catch(() => {});
  try {
    await decoder;
  } catch {
    closeScanner();
    showNote("The scanner could not be loaded. Take a photo of the barcode instead, or type the digits.");
    return;
  }
  if (!current.active) return;
  current.hint = setTimeout(() => {
    status.textContent = "Hold steady about 15 cm away with light on the barcode, or Close and take a photo.";
  }, HINT_AFTER_MS);
  scanLoop(current);
}

async function stillImageData(file) {
  const bitmap = await createImageBitmap(file);
  try {
    const scale = Math.min(1, STILL_MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const width = Math.round(bitmap.width * scale);
    const height = Math.round(bitmap.height * scale);
    canvas.width = width;
    canvas.height = height;
    canvasContext.drawImage(bitmap, 0, 0, width, height);
    return canvasContext.getImageData(0, 0, width, height);
  } finally {
    bitmap.close();
  }
}

async function readPhoto() {
  const file = photoInput.files[0];
  if (!file) return;
  showNote("Reading the photo…");
  try {
    const imageData = await stillImageData(file);
    const results = await (await loadDecoder()).readBarcodes(imageData, READER_OPTIONS);
    const hit = results.find((result) => result.isValid);
    if (hit) {
      navigator.vibrate?.(60);
      showResult(hit.text);
    } else {
      showNote(
        "No barcode found in that photo. Get closer, keep the barcode flat and sharp with light on it, " +
          "and try again, or type the digits."
      );
    }
  } catch (error) {
    showNote(`That photo could not be read (${error?.message ?? error}). Try again, or type the digits.`);
  } finally {
    photoInput.value = "";
  }
}

if (dialog && video && guide && status) {
  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-scan-open]")) openScanner();
    else if (event.target.closest("[data-scan-close]")) closeScanner();
  });
  dialog.addEventListener("close", stopCamera); // Esc, Close and a finished scan all end up here
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) closeScanner();
  });
  window.addEventListener("pagehide", closeScanner);
  photoInput?.addEventListener("change", readPhoto);

  const problem = cameraProblem();
  if (problem) showNote(problem);
  else if (dialog.dataset.autoscan === "1") openScanner();
}
