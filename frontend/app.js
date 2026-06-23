/**
 * Automated Test Execution Platform — frontend controller.
 *
 * Handles: drag-and-drop / click upload, client-side pre-validation,
 * calling /api/upload -> /api/execute/{session_id}, rendering
 * progress + results, and triggering the report download.
 */

(() => {
  "use strict";

  const API_BASE = "/api";
  const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024; // 100 MB, mirrors backend config
  const ALLOWED_EXTENSIONS = [".py", ".c", ".java", ".zip"];

  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const fileListEl = document.getElementById("fileList");
  const errorBox = document.getElementById("errorBox");
  const runButton = document.getElementById("runButton");
  const progressPanel = document.getElementById("progressPanel");
  const progressSteps = document.getElementById("progressSteps");
  const resultsPanel = document.getElementById("resultsPanel");
  const resultsBody = document.getElementById("resultsBody");
  const summaryChips = document.getElementById("summaryChips");
  const downloadButton = document.getElementById("downloadButton");
  const sandboxStatusDot = document.querySelector("#sandboxStatus .status-dot");
  const sandboxStatusText = document.getElementById("sandboxStatusText");

  /** @type {File[]} */
  let stagedFiles = [];
  let currentSessionId = null;

  // ------------------------------------------------------------------
  // Health check (sandbox availability indicator)
  // ------------------------------------------------------------------
  async function checkHealth() {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (!res.ok) throw new Error("health check failed");
      const data = await res.json();
      if (data.docker_sandbox_available) {
        sandboxStatusDot.className = "status-dot status-dot--ok";
        sandboxStatusText.textContent = "Sandbox: Docker isolation active";
      } else {
        sandboxStatusDot.className = "status-dot status-dot--warn";
        sandboxStatusText.textContent = "Sandbox: local fallback (degraded isolation)";
      }
    } catch (_err) {
      sandboxStatusDot.className = "status-dot status-dot--warn";
      sandboxStatusText.textContent = "Sandbox status unavailable";
    }
  }

  // ------------------------------------------------------------------
  // File staging + client-side validation
  // ------------------------------------------------------------------
  function extensionOf(filename) {
    const idx = filename.lastIndexOf(".");
    return idx === -1 ? "" : filename.slice(idx).toLowerCase();
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function clearError() {
    errorBox.hidden = true;
    errorBox.textContent = "";
  }

  function addFiles(fileArray) {
    clearError();
    const rejected = [];

    for (const file of fileArray) {
      const ext = extensionOf(file.name);

      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        rejected.push(`${file.name} — unsupported type (${ext || "no extension"})`);
        continue;
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        rejected.push(`${file.name} — exceeds 100 MB limit`);
        continue;
      }
      // Avoid duplicate staging of the same filename.
      if (stagedFiles.some((f) => f.name === file.name && f.size === file.size)) {
        continue;
      }
      stagedFiles.push(file);
    }

    if (rejected.length) {
      showError(`Rejected ${rejected.length} file(s):\n${rejected.join("\n")}`);
    }

    renderFileList();
  }

  function removeFile(index) {
    stagedFiles.splice(index, 1);
    renderFileList();
  }

  function renderFileList() {
    fileListEl.innerHTML = "";
    stagedFiles.forEach((file, index) => {
      const li = document.createElement("li");

      const nameSpan = document.createElement("span");
      nameSpan.className = "file-name";
      nameSpan.textContent = file.name;

      const metaWrap = document.createElement("span");
      metaWrap.className = "file-meta";

      const tag = document.createElement("span");
      tag.className = "file-tag";
      tag.textContent = extensionOf(file.name).replace(".", "") || "file";

      const size = document.createElement("span");
      size.textContent = formatBytes(file.size);

      const removeBtn = document.createElement("button");
      removeBtn.className = "file-remove";
      removeBtn.type = "button";
      removeBtn.setAttribute("aria-label", `Remove ${file.name}`);
      removeBtn.textContent = "✕";
      removeBtn.addEventListener("click", () => removeFile(index));

      metaWrap.append(tag, size, removeBtn);
      li.append(nameSpan, metaWrap);
      fileListEl.appendChild(li);
    });

    runButton.disabled = stagedFiles.length === 0;
  }

  // ------------------------------------------------------------------
  // Drag & drop wiring
  // ------------------------------------------------------------------
  dropzone.addEventListener("click", (e) => {
    // Avoid double-trigger when clicking the native label/input itself.
    if (e.target !== fileInput) {
      fileInput.click();
    }
  });

  dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });

  fileInput.addEventListener("change", (e) => {
    addFiles(Array.from(e.target.files || []));
    fileInput.value = ""; // allow re-selecting the same file later
  });

  ["dragenter", "dragover"].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.add("is-dragover");
    });
  });

  ["dragleave", "drop"].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.remove("is-dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const files = Array.from(e.dataTransfer.files || []);
    addFiles(files);
  });

  // ------------------------------------------------------------------
  // Progress step UI helpers
  // ------------------------------------------------------------------
  function setStep(stepName, state) {
    const li = progressSteps.querySelector(`[data-step="${stepName}"]`);
    if (!li) return;
    li.classList.remove("is-active", "is-done");
    if (state) li.classList.add(state);
  }

  function resetProgress() {
    progressSteps.querySelectorAll("li").forEach((li) => {
      li.classList.remove("is-active", "is-done");
    });
  }

  // ------------------------------------------------------------------
  // Main run flow: upload -> execute -> render results
  // ------------------------------------------------------------------
  async function runTests() {
    clearError();
    resultsPanel.hidden = true;
    progressPanel.hidden = false;
    resetProgress();

    runButton.disabled = true;
    runButton.querySelector(".btn__label").textContent = "Running…";
    runButton.querySelector(".btn__spinner").hidden = false;

    try {
      setStep("upload", "is-active");
      const formData = new FormData();
      stagedFiles.forEach((file) => formData.append("files", file));

      const uploadRes = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!uploadRes.ok) {
        const errBody = await safeJson(uploadRes);
        throw new Error(errBody?.detail || `Upload failed (HTTP ${uploadRes.status})`);
      }

      const uploadData = await uploadRes.json();
      currentSessionId = uploadData.session_id;
      setStep("upload", "is-done");
      setStep("detect", "is-done"); // detection happens server-side during upload

      setStep("execute", "is-active");
      const executeRes = await fetch(`${API_BASE}/execute/${currentSessionId}`, {
        method: "POST",
      });

      if (!executeRes.ok) {
        const errBody = await safeJson(executeRes);
        throw new Error(errBody?.detail || `Execution failed (HTTP ${executeRes.status})`);
      }

      const executeData = await executeRes.json();
      setStep("execute", "is-done");

      setStep("report", "is-active");
      await new Promise((resolve) => setTimeout(resolve, 250)); // perceptible step
      setStep("report", "is-done");

      renderResults(executeData);
    } catch (err) {
      showError(err.message || "An unexpected error occurred.");
      progressPanel.hidden = true;
    } finally {
      runButton.disabled = stagedFiles.length === 0;
      runButton.querySelector(".btn__label").textContent = "Execute Tests";
      runButton.querySelector(".btn__spinner").hidden = true;
    }
  }

  async function safeJson(response) {
    try {
      return await response.json();
    } catch (_err) {
      return null;
    }
  }

  function renderResults(executeData) {
    resultsBody.innerHTML = "";
    summaryChips.innerHTML = "";

    const passChip = document.createElement("span");
    passChip.className = "chip chip--pass";
    passChip.textContent = `${executeData.passed} PASS`;

    const failChip = document.createElement("span");
    failChip.className = "chip chip--fail";
    failChip.textContent = `${executeData.failed} FAIL`;

    const totalChip = document.createElement("span");
    totalChip.className = "chip";
    totalChip.textContent = `${executeData.total} total`;

    summaryChips.append(totalChip, passChip, failChip);

    executeData.results.forEach((row) => {
      const tr = document.createElement("tr");

      const tdName = document.createElement("td");
      tdName.textContent = row["File Name"];

      const tdTc = document.createElement("td");
      tdTc.textContent = row["Test Case No"];

      const tdResult = document.createElement("td");
      const pill = document.createElement("span");
      const isPass = row["Result"] === "PASS";
      pill.className = `result-pill ${isPass ? "result-pill--pass" : "result-pill--fail"}`;
      pill.textContent = row["Result"];
      tdResult.appendChild(pill);

      tr.append(tdName, tdTc, tdResult);
      resultsBody.appendChild(tr);
    });

    resultsPanel.hidden = false;
    resultsPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  downloadButton.addEventListener("click", () => {
    if (!currentSessionId) return;
    window.location.href = `${API_BASE}/download-report/${currentSessionId}`;
  });

  runButton.addEventListener("click", runTests);

  // ------------------------------------------------------------------
  // Init
  // ------------------------------------------------------------------
  checkHealth();
  renderFileList();
})();
