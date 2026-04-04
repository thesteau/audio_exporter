document.addEventListener("DOMContentLoaded", () => {
  const dropzone = document.querySelector("[data-dropzone]");
  const fileInput = document.querySelector("[data-file-input]");
  const summary = document.querySelector("[data-file-summary]");
  const uploadForm = document.querySelector("[data-upload-form]");
  const convertForm = document.querySelector("[data-convert-form]");
  const uploadSubmit = document.querySelector("[data-upload-submit]");
  const convertSubmit = document.querySelector("[data-convert-submit]");
  const activityTray = document.querySelector("[data-activity-tray]");

  const uploadedFileRows = () => Array.from(document.querySelectorAll("[data-uploaded-file-row]"));
  const formatSelect = convertForm?.querySelector('select[name="output_format"]') ?? null;
  let activityCount = 0;

  const updateSummary = (files) => {
    if (!summary) {
      return;
    }

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

  const formatBytes = (bytes) => {
    if (!Number.isFinite(bytes) || bytes <= 0) {
      return "0 B";
    }

    const units = ["B", "KB", "MB", "GB", "TB"];
    let value = bytes;
    let unitIndex = 0;
    while (value >= 1024 && unitIndex < units.length - 1) {
      value /= 1024;
      unitIndex += 1;
    }
    return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
  };

  const setButtonBusy = (button, isBusy, busyText) => {
    if (!button) {
      return;
    }

    if (!button.dataset.defaultLabel) {
      button.dataset.defaultLabel = button.textContent.trim();
    }

    if (isBusy) {
      button.dataset.restoreDisabled = button.disabled ? "true" : "false";
      button.disabled = true;
    } else {
      button.disabled = button.dataset.restoreDisabled === "true";
      delete button.dataset.restoreDisabled;
    }
    button.textContent = isBusy ? busyText : button.dataset.defaultLabel;
  };

  const createActivity = ({ title, detail, tone = "running" }) => {
    if (!activityTray) {
      return null;
    }

    activityCount += 1;
    const card = document.createElement("section");
    card.className = `activity-card is-${tone}`;
    card.dataset.activityId = `activity-${activityCount}`;

    const header = document.createElement("div");
    header.className = "activity-header";

    const titleElement = document.createElement("h3");
    titleElement.className = "activity-title";
    titleElement.textContent = title;

    const badge = document.createElement("span");
    badge.className = "activity-badge";
    badge.textContent = tone === "running" ? "Working" : "Ready";

    header.append(titleElement, badge);

    const detailElement = document.createElement("p");
    detailElement.className = "activity-detail";
    detailElement.textContent = detail;

    const progress = document.createElement("div");
    progress.className = "activity-progress";

    const progressBar = document.createElement("div");
    progressBar.className = "activity-progress-bar";
    progress.append(progressBar);

    const list = document.createElement("ul");
    list.className = "activity-file-list";

    card.append(header, detailElement, progress, list);
    activityTray.append(card);

    return {
      badge,
      card,
      detailElement,
      fileItems: new Map(),
      list,
      progress,
      progressBar,
      titleElement,
    };
  };

  const setActivityTone = (activity, tone, badgeText) => {
    if (!activity) {
      return;
    }

    activity.card.classList.remove("is-running", "is-success", "is-warning", "is-error");
    activity.card.classList.add(`is-${tone}`);
    activity.badge.textContent = badgeText;
  };

  const updateActivity = (activity, { title, detail, progressPercent, indeterminate, tone, badgeText }) => {
    if (!activity) {
      return;
    }

    if (title) {
      activity.titleElement.textContent = title;
    }
    if (detail) {
      activity.detailElement.textContent = detail;
    }
    if (typeof progressPercent === "number") {
      activity.progressBar.style.width = `${Math.max(0, Math.min(progressPercent, 100))}%`;
    }

    activity.progress.classList.toggle("is-indeterminate", Boolean(indeterminate));
    if (tone && badgeText) {
      setActivityTone(activity, tone, badgeText);
    }
  };

  const ensureFileItem = (activity, key, label) => {
    if (!activity) {
      return null;
    }

    const existing = activity.fileItems.get(key);
    if (existing) {
      if (label) {
        existing.name.textContent = label;
      }
      return existing;
    }

    const item = document.createElement("li");
    item.className = "activity-file is-queued";

    const info = document.createElement("div");
    info.className = "activity-file-info";

    const name = document.createElement("span");
    name.className = "activity-file-name";
    name.textContent = label;

    const meta = document.createElement("span");
    meta.className = "activity-file-meta";
    meta.textContent = "Waiting";

    info.append(name, meta);

    const status = document.createElement("span");
    status.className = "activity-file-status";
    status.textContent = "Queued";

    item.append(info, status);
    activity.list.append(item);

    const fileItem = { item, meta, name, status };
    activity.fileItems.set(key, fileItem);
    return fileItem;
  };

  const setFileStatus = (activity, key, { label, tone, detail, statusText }) => {
    const fileItem = ensureFileItem(activity, key, label);
    if (!fileItem) {
      return;
    }

    fileItem.item.classList.remove("is-queued", "is-processing", "is-success", "is-warning", "is-error");
    fileItem.item.classList.add(`is-${tone}`);
    if (label) {
      fileItem.name.textContent = label;
    }
    fileItem.meta.textContent = detail;
    fileItem.status.textContent = statusText;
  };

  const dismissActivity = (activity, delay = 1800) => {
    if (!activity) {
      return;
    }

    window.setTimeout(() => {
      activity.card.classList.add("is-closing");
      window.setTimeout(() => activity.card.remove(), 280);
    }, delay);
  };

  const handleUploadFailure = (activity, files, message) => {
    files.forEach((file, index) => {
      setFileStatus(activity, String(index), {
        label: file.name,
        tone: "error",
        detail: message,
        statusText: "Error",
      });
    });
    updateActivity(activity, {
      detail: message,
      progressPercent: 100,
      tone: "error",
      badgeText: "Error",
    });
  };

  if (dropzone && fileInput) {
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
  }

  if (uploadForm && fileInput && activityTray) {
    uploadForm.addEventListener("submit", (event) => {
      event.preventDefault();

      const files = Array.from(fileInput.files || []);
      if (files.length === 0) {
        const emptyActivity = createActivity({
          title: "Upload needed",
          detail: "Choose at least one file before uploading.",
          tone: "warning",
        });
        updateActivity(emptyActivity, {
          progressPercent: 100,
          tone: "warning",
          badgeText: "Check",
        });
        dismissActivity(emptyActivity, 2200);
        return;
      }

      const activity = createActivity({
        title: "Uploading files",
        detail: `Preparing ${files.length} file(s) for upload...`,
      });
      files.forEach((file, index) => {
        setFileStatus(activity, String(index), {
          label: file.name,
          tone: "queued",
          detail: "Waiting to upload",
          statusText: "Queued",
        });
      });

      setButtonBusy(uploadSubmit, true, "Uploading...");
      setButtonBusy(convertSubmit, true, "Convert Uploaded Files");

      const xhr = new XMLHttpRequest();
      xhr.open("POST", uploadForm.dataset.uploadAsyncUrl || uploadForm.action);
      xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");

      xhr.upload.addEventListener("loadstart", () => {
        files.forEach((file, index) => {
          setFileStatus(activity, String(index), {
            label: file.name,
            tone: "processing",
            detail: "Uploading...",
            statusText: "Sending",
          });
        });
      });

      xhr.upload.addEventListener("progress", (progressEvent) => {
        const progressPercent = progressEvent.lengthComputable
          ? Math.round((progressEvent.loaded / progressEvent.total) * 100)
          : 0;
        const detail = progressEvent.lengthComputable
          ? `Uploading ${files.length} file(s): ${progressPercent}% of ${formatBytes(progressEvent.total)}`
          : `Uploading ${files.length} file(s)...`;

        updateActivity(activity, {
          detail,
          progressPercent,
          tone: "running",
          badgeText: "Working",
        });
      });

      xhr.upload.addEventListener("load", () => {
        updateActivity(activity, {
          detail: "Upload received. Checking each file now...",
          progressPercent: 100,
          tone: "running",
          badgeText: "Working",
        });
      });

      xhr.addEventListener("error", () => {
        handleUploadFailure(activity, files, "Upload failed. Please try again.");
        setButtonBusy(uploadSubmit, false, "Uploading...");
        setButtonBusy(convertSubmit, false, "Convert Uploaded Files");
      });

      xhr.addEventListener("load", () => {
        let payload = null;
        try {
          payload = JSON.parse(xhr.responseText || "{}");
        } catch (error) {
          payload = null;
        }

        if (!payload) {
          handleUploadFailure(activity, files, "Upload finished, but the server response could not be read.");
          setButtonBusy(uploadSubmit, false, "Uploading...");
          setButtonBusy(convertSubmit, false, "Convert Uploaded Files");
          return;
        }

        const tone = payload.success
          ? payload.skipped_count > 0
            ? "warning"
            : "success"
          : "error";

        files.forEach((file, index) => {
          const result = payload.results.find((entry) => entry.index === index);
          if (!result) {
            setFileStatus(activity, String(index), {
              label: file.name,
              tone: payload.success ? "success" : "error",
              detail: payload.success ? "Uploaded" : payload.message,
              statusText: payload.success ? "Uploaded" : "Error",
            });
            return;
          }

          if (result.status === "uploaded") {
            setFileStatus(activity, String(index), {
              label: result.source_name,
              tone: "success",
              detail: result.stored_name === result.source_name ? "Uploaded successfully" : `Saved as ${result.stored_name}`,
              statusText: "Uploaded",
            });
            return;
          }

          setFileStatus(activity, String(index), {
            label: result.source_name,
            tone: "warning",
            detail: result.reason || "Skipped",
            statusText: "Skipped",
          });
        });

        updateActivity(activity, {
          detail: payload.message,
          progressPercent: 100,
          tone,
          badgeText: tone === "success" ? "Done" : tone === "warning" ? "Mixed" : "Error",
        });

        if (!payload.success) {
          setButtonBusy(uploadSubmit, false, "Uploading...");
          setButtonBusy(convertSubmit, false, "Convert Uploaded Files");
          return;
        }

        fileInput.value = "";
        updateSummary(fileInput.files);
        dismissActivity(activity, 1600);
        window.setTimeout(() => window.location.reload(), 1400);
      });

      xhr.send(new FormData(uploadForm));
    });
  }

  if (convertForm && activityTray) {
    convertForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (convertSubmit?.disabled) {
        return;
      }

      const pendingFiles = uploadedFileRows().map((row) => row.dataset.fileName).filter(Boolean);
      if (pendingFiles.length === 0) {
        const emptyActivity = createActivity({
          title: "Nothing to convert",
          detail: "Upload at least one file before converting.",
          tone: "warning",
        });
        updateActivity(emptyActivity, {
          progressPercent: 100,
          tone: "warning",
          badgeText: "Check",
        });
        dismissActivity(emptyActivity, 2200);
        return;
      }

      const outputLabel = formatSelect?.selectedOptions?.[0]?.textContent?.trim() || "Selected Format";
      const activity = createActivity({
        title: `Converting to ${outputLabel}`,
        detail: `Queued ${pendingFiles.length} uploaded file(s).`,
      });
      pendingFiles.forEach((fileName) => {
        setFileStatus(activity, fileName, {
          label: fileName,
          tone: "queued",
          detail: "Waiting in queue",
          statusText: "Queued",
        });
      });

      setButtonBusy(uploadSubmit, true, "Upload Files");
      setButtonBusy(convertSubmit, true, "Converting...");
      if (formatSelect) {
        formatSelect.disabled = true;
      }

      const completedFiles = new Set();
      const totalFiles = pendingFiles.length;
      let sawCompleteEvent = false;

      const refreshProgress = (detail) => {
        const progressPercent = totalFiles > 0 ? Math.round((completedFiles.size / totalFiles) * 100) : 0;
        updateActivity(activity, {
          detail,
          progressPercent,
          indeterminate: totalFiles === 0,
          tone: "running",
          badgeText: "Working",
        });
      };

      try {
        const response = await fetch(convertForm.dataset.processStreamUrl || convertForm.action, {
          method: "POST",
          body: new FormData(convertForm),
          headers: { "X-Requested-With": "XMLHttpRequest" },
        });

        const contentType = response.headers.get("content-type") || "";
        if (!response.ok || contentType.includes("application/json")) {
          const payload = await response.json().catch(() => ({ message: "Conversion could not start." }));
          throw new Error(payload.message || "Conversion could not start.");
        }

        if (!response.body) {
          throw new Error("Live conversion progress is not available in this browser.");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        const handleEvent = (payload) => {
          if (!payload || !payload.event) {
            return;
          }

          if (payload.event === "start") {
            refreshProgress(payload.message || `Converting to ${outputLabel}...`);
            return;
          }

          if (payload.event === "log") {
            refreshProgress(payload.message || "Processing...");
            return;
          }

          if (payload.event === "error") {
            updateActivity(activity, {
              detail: payload.message || "Processing failed.",
              progressPercent: 100,
              tone: "error",
              badgeText: "Error",
            });
            return;
          }

          if (payload.event === "file") {
            const key = payload.source_name || payload.raw || `file-${completedFiles.size + 1}`;
            if (payload.status === "processing") {
              setFileStatus(activity, key, {
                label: payload.source_name || key,
                tone: "processing",
                detail: payload.output_name ? `Writing ${payload.output_name}` : "Converting...",
                statusText: "Converting",
              });
              refreshProgress(`Converting ${payload.source_name || "file"}...`);
              return;
            }

            if (payload.status === "success") {
              completedFiles.add(key);
              setFileStatus(activity, key, {
                label: payload.source_name || key,
                tone: "success",
                detail: "Finished successfully",
                statusText: "Done",
              });
              refreshProgress(`${completedFiles.size} of ${totalFiles} file(s) finished.`);
              return;
            }

            if (payload.status === "skipped") {
              completedFiles.add(key);
              setFileStatus(activity, key, {
                label: payload.source_name || key,
                tone: "warning",
                detail: "Already converted",
                statusText: "Skipped",
              });
              refreshProgress(`${completedFiles.size} of ${totalFiles} file(s) resolved.`);
              return;
            }

            if (payload.status === "error") {
              completedFiles.add(key);
              setFileStatus(activity, key, {
                label: payload.source_name || key,
                tone: "error",
                detail: "Conversion failed",
                statusText: "Error",
              });
              refreshProgress(`${completedFiles.size} of ${totalFiles} file(s) resolved.`);
            }
            return;
          }

          if (payload.event === "complete") {
            sawCompleteEvent = true;
            const tone = payload.success
              ? payload.failed > 0
                ? "error"
                : payload.skipped > 0
                  ? "warning"
                  : "success"
              : "error";

            updateActivity(activity, {
              detail: payload.message,
              progressPercent: 100,
              tone,
              badgeText: tone === "success" ? "Done" : tone === "warning" ? "Mixed" : "Error",
            });

            dismissActivity(activity, 1700);
            window.setTimeout(() => window.location.reload(), 1500);
          }
        };

        while (true) {
          const { done, value } = await reader.read();
          buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          lines
            .map((line) => line.trim())
            .filter(Boolean)
            .forEach((line) => {
              try {
                handleEvent(JSON.parse(line));
              } catch (error) {
                refreshProgress(line);
              }
            });

          if (done) {
            if (buffer.trim()) {
              try {
                handleEvent(JSON.parse(buffer.trim()));
              } catch (error) {
                refreshProgress(buffer.trim());
              }
            }
            break;
          }
        }

        if (!sawCompleteEvent) {
          throw new Error("Conversion finished without a completion signal from the server.");
        }
      } catch (error) {
        updateActivity(activity, {
          detail: error.message || "Conversion failed. Please try again.",
          progressPercent: 100,
          tone: "error",
          badgeText: "Error",
        });
        setButtonBusy(uploadSubmit, false, "Upload Files");
        setButtonBusy(convertSubmit, false, "Converting...");
        if (formatSelect) {
          formatSelect.disabled = false;
        }
      }
    });
  }

  updateSummary(fileInput?.files);
});
