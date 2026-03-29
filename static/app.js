document.addEventListener("DOMContentLoaded", () => {
  const dropzone = document.querySelector("[data-dropzone]");
  const fileInput = document.querySelector("[data-file-input]");
  const summary = document.querySelector("[data-file-summary]");

  if (!dropzone || !fileInput || !summary) {
    return;
  }

  const updateSummary = (files) => {
    if (!files || files.length === 0) {
      summary.textContent = "No files selected yet.";
      return;
    }

    if (files.length === 1) {
      summary.textContent = `Selected: ${files[0].name}`;
      return;
    }

    summary.textContent = `${files.length} files selected.`;
  };

  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.add("is-active");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      if (eventName === "drop") {
        fileInput.files = event.dataTransfer.files;
        updateSummary(fileInput.files);
      }
      dropzone.classList.remove("is-active");
    });
  });

  fileInput.addEventListener("change", () => updateSummary(fileInput.files));
});
