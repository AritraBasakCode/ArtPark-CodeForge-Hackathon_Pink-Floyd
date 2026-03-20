const resumeInput = document.getElementById("resume");
const uploadZone  = document.getElementById("upload-zone");
const fileNameEl  = document.getElementById("file-name");

if (resumeInput) {
  resumeInput.addEventListener("change", () => {
    const file = resumeInput.files[0];
    if (!file) return;
    uploadZone.classList.add("has-file");
    fileNameEl.textContent = "✓ " + file.name;
  });

  uploadZone.addEventListener("dragover", e => {
    e.preventDefault();
    uploadZone.classList.add("dragover");
  });

  uploadZone.addEventListener("dragleave", () => {
    uploadZone.classList.remove("dragover");
  });

  uploadZone.addEventListener("drop", e => {
    e.preventDefault();
    uploadZone.classList.remove("dragover");
    const file = e.dataTransfer.files[0];
    if (file) {
      uploadZone.classList.add("has-file");
      fileNameEl.textContent = "✓ " + file.name;
    }
  });
}

document.getElementById("analyzeBtn").addEventListener("click", () => {
  window.location.href = "skill-gap.html";
});
