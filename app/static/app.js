document.addEventListener("DOMContentLoaded", () => {
  const dropzone = document.querySelector("[data-dropzone]");
  const fileInput = document.querySelector("[data-file-input]");
  const summary = document.querySelector("[data-file-summary]");
  const uploadForm = document.querySelector("[data-upload-form]");
  const convertForm = document.querySelector("[data-convert-form]");
  const uploadSubmit = document.querySelector("[data-upload-submit]");
  const convertSubmit = document.querySelector("[data-convert-submit]");
  const activityTray = document.querySelector("[data-activity-tray]");
  const serverFlashes = document.querySelector("[data-server-flashes]");

  const uploadedFileRows = () => Array.from(document.querySelectorAll("[data-uploaded-file-row]"));
  const formatSelect = convertForm?.querySelector('select[name="output_format"]') ?? null;
  let activityCount = 0;

  const updateSummary = (files) => {
    if (!summary) {
      return;
    }

    if (!files || files.length === 0) {
      summary.textContent = "No files selected";
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

  const createActivity = ({ title, detail, tone = "running", showProgress = true, showList = true }) => {
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

    if (!showProgress) {
      card.classList.add("has-no-progress");
    }
    if (!showList) {
      card.classList.add("has-no-list");
    }

    card.append(header, detailElement);
    if (showProgress) {
      card.append(progress);
    }
    if (showList) {
      card.append(list);
    }
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

  const syncConvertAvailability = (nextDocument) => {
    if (!convertSubmit) {
      return;
    }

    const nextConvertSubmit = nextDocument.querySelector("[data-convert-submit]");
    if (!nextConvertSubmit) {
      return;
    }

    convertSubmit.disabled = nextConvertSubmit.disabled;
  };

  const syncFilePanels = (nextDocument) => {
    const currentGrid = document.querySelector(".file-grid");
    const nextGrid = nextDocument.querySelector(".file-grid");
    if (!currentGrid || !nextGrid) {
      return;
    }

    currentGrid.replaceWith(nextGrid);
  };

  const refreshPageState = async () => {
    const response = await fetch(window.location.pathname, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error("The page could not be refreshed.");
    }

    const html = await response.text();
    const parser = new DOMParser();
    const nextDocument = parser.parseFromString(html, "text/html");

    syncFilePanels(nextDocument);
    syncConvertAvailability(nextDocument);
    readServerClock();
    updateRetention();
  };

  // Retention tags: server renders epoch seconds; we tick them locally, corrected for clock skew.
  let serverClockOffset = 0;
  let retentionRefreshPending = false;

  const readServerClock = () => {
    const grid = document.querySelector("[data-file-grid]");
    const serverNow = Number(grid?.dataset.serverNow);
    if (Number.isFinite(serverNow)) {
      serverClockOffset = serverNow * 1000 - Date.now();
    }
  };

  const formatRemaining = (seconds) => {
    const totalMinutes = Math.max(0, Math.floor(seconds / 60));
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    if (hours) {
      return `${hours}h ${minutes}m`;
    }
    return minutes ? `${minutes}m` : "<1m";
  };

  const retentionLabels = { active: "Active", expiring: "Expiring", deleting: "Deleting" };

  const updateRetention = () => {
    const grid = document.querySelector("[data-file-grid]");
    if (!grid) {
      return;
    }

    const warning = Number(grid.dataset.expiryWarning);
    const critical = Number(grid.dataset.expiryCritical);
    const now = (Date.now() + serverClockOffset) / 1000;
    let anyGone = false;

    grid.querySelectorAll("[data-retention]").forEach((cell) => {
      const expiresAt = Number(cell.dataset.expiresAt);
      const deleteAt = Number(cell.dataset.deleteAt);
      const remaining = expiresAt - now;
      const state = remaining <= critical ? "deleting" : remaining <= warning ? "expiring" : "active";

      const tag = cell.querySelector("[data-retention-tag]");
      if (tag) {
        tag.className = `tag tag-${state}`;
        tag.textContent = retentionLabels[state];
      }
      const remainingElement = cell.querySelector("[data-retention-remaining]");
      if (remainingElement) {
        remainingElement.textContent = formatRemaining(deleteAt - now);
      }
      const deleteDate = new Date(deleteAt * 1000 - serverClockOffset);
      cell.title = `Deleted around ${deleteDate.toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}`;

      if (deleteAt <= now) {
        anyGone = true;
      }
    });

    // A sweep has likely run: pull the fresh list so deleted files disappear.
    if (anyGone && !retentionRefreshPending && !document.hidden) {
      retentionRefreshPending = true;
      window.setTimeout(() => {
        refreshPageState()
          .catch(() => {})
          .finally(() => {
            retentionRefreshPending = false;
          });
      }, 15000);
    }
  };

  readServerClock();
  updateRetention();
  window.setInterval(updateRetention, 30000);

  const showFlashToast = (category, message) => {
    const toneMap = {
      success: "success",
      warning: "warning",
      danger: "error",
      info: "running",
    };
    const badgeMap = {
      success: "Done",
      warning: "Check",
      danger: "Error",
      info: "Notice",
    };
    const titleMap = {
      success: "Update",
      warning: "Attention",
      danger: "Problem",
      info: "Update",
    };
    const activity = createActivity({
      title: titleMap[category] || "Update",
      detail: message,
      tone: toneMap[category] || "running",
      showProgress: false,
      showList: false,
    });

    if (!activity) {
      return;
    }

    updateActivity(activity, {
      tone: toneMap[category] || "running",
      badgeText: badgeMap[category] || "Notice",
    });
    dismissActivity(activity, category === "danger" ? 4200 : 3000);
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
      setButtonBusy(convertSubmit, true, "Convert");

      const uploadUrl = uploadForm.dataset.uploadAsyncUrl || uploadForm.action;
      const maxUploadBytes = Number(uploadForm.dataset.maxUploadBytes) || Infinity;
      const totalBytes = files.reduce((sum, file) => sum + file.size, 0) || 1;
      const maxAttempts = 3;

      // One request per file: a failure only costs that file, and it can be retried alone.
      // Resolves { status, payload }; status 0 means no response (network drop, reset).
      const sendFile = (file, onProgress) =>
        new Promise((resolve) => {
          const xhr = new XMLHttpRequest();
          xhr.open("POST", uploadUrl);
          xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
          xhr.upload.addEventListener("progress", (progressEvent) => {
            if (progressEvent.lengthComputable) {
              onProgress(progressEvent.loaded / progressEvent.total);
            }
          });
          xhr.addEventListener("load", () => {
            let payload = null;
            try {
              payload = JSON.parse(xhr.responseText || "null");
            } catch (error) {
              payload = null;
            }
            resolve({ status: xhr.status, payload });
          });
          xhr.addEventListener("error", () => resolve({ status: 0, payload: null }));
          xhr.addEventListener("abort", () => resolve({ status: 0, payload: null }));

          const body = new FormData();
          body.append("files", file, file.name);
          xhr.send(body);
        });

      // Retry dropped connections and server hiccups; never retry a definite answer (4xx, disk full).
      const isRetryable = (status) => status === 0 || (status >= 500 && status !== 507);
      const wait = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

      const uploadAll = async () => {
        const counts = { uploaded: 0, skipped: 0, failed: 0 };
        let finishedBytes = 0;

        for (const [index, file] of files.entries()) {
          const key = String(index);
          const detailPrefix = files.length > 1 ? `File ${index + 1} of ${files.length}` : "Uploading";

          if (file.size > maxUploadBytes) {
            counts.failed += 1;
            finishedBytes += file.size;
            setFileStatus(activity, key, {
              label: file.name,
              tone: "error",
              detail: `Too large (limit ${formatBytes(maxUploadBytes)})`,
              statusText: "Error",
            });
            continue;
          }

          let result = { status: 0, payload: null };
          for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
            setFileStatus(activity, key, {
              label: file.name,
              tone: "processing",
              detail: attempt > 1 ? `Retrying (${attempt}/${maxAttempts})...` : "Uploading...",
              statusText: "Sending",
            });
            result = await sendFile(file, (fraction) => {
              setFileStatus(activity, key, {
                label: file.name,
                tone: "processing",
                detail: fraction >= 1 ? "Checking audio..." : `${Math.round(fraction * 100)}% of ${formatBytes(file.size)}`,
                statusText: "Sending",
              });
              updateActivity(activity, {
                detail: `${detailPrefix}...`,
                progressPercent: ((finishedBytes + fraction * file.size) / totalBytes) * 100,
                tone: "running",
                badgeText: "Working",
              });
            });
            if (!isRetryable(result.status) || attempt === maxAttempts) {
              break;
            }
            await wait(1000 * attempt);
          }
          finishedBytes += file.size;

          const entry = result.payload?.results?.[0];
          if (entry?.status === "uploaded") {
            counts.uploaded += 1;
            setFileStatus(activity, key, {
              label: file.name,
              tone: "success",
              detail: entry.stored_name === entry.source_name ? "Uploaded" : `Saved as ${entry.stored_name}`,
              statusText: "Done",
            });
          } else if (entry?.status === "skipped") {
            counts.skipped += 1;
            setFileStatus(activity, key, {
              label: file.name,
              tone: "warning",
              detail: entry.reason || "Skipped",
              statusText: "Skipped",
            });
          } else {
            counts.failed += 1;
            setFileStatus(activity, key, {
              label: file.name,
              tone: "error",
              detail:
                result.payload?.message ||
                (result.status === 0 ? "Connection lost" : `Server error (${result.status})`),
              statusText: "Error",
            });
          }
        }
        return counts;
      };

      void uploadAll().then(async (counts) => {
        const parts = [`${counts.uploaded} uploaded`];
        if (counts.skipped) {
          parts.push(`${counts.skipped} skipped`);
        }
        if (counts.failed) {
          parts.push(`${counts.failed} failed`);
        }
        const tone = counts.failed || counts.uploaded === 0 ? "error" : counts.skipped ? "warning" : "success";
        updateActivity(activity, {
          detail: `${parts.join(", ")}.`,
          progressPercent: 100,
          tone,
          badgeText: tone === "success" ? "Done" : tone === "warning" ? "Mixed" : "Error",
        });

        // Always clear: re-sending the same selection would duplicate the files that did upload.
        fileInput.value = "";
        updateSummary(fileInput.files);
        setButtonBusy(uploadSubmit, false, "Uploading...");
        setButtonBusy(convertSubmit, false, "Convert");

        if (counts.uploaded) {
          try {
            await refreshPageState();
          } catch (error) {
            showFlashToast("warning", error.message || "Uploaded, but the file list could not be refreshed.");
          }
        }
        // Keep problem reports on screen long enough to read.
        dismissActivity(activity, tone === "success" ? 3200 : 8000);
      });
    });
  }

  if (convertForm && activityTray) {
    convertForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (convertSubmit?.disabled) {
        return;
      }

      if (uploadedFileRows().length === 0) {
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
        detail: "Starting...",
      });
      updateActivity(activity, { indeterminate: true });

      setButtonBusy(uploadSubmit, true, "Upload");
      setButtonBusy(convertSubmit, true, "Converting...");
      if (formatSelect) {
        formatSelect.disabled = true;
      }

      const completedFiles = new Set();
      // The server sends the files this pass will convert (already-converted ones are left out).
      let pendingFiles = [];
      let totalFiles = 0;
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
          const startError = new Error(payload.message || "Conversion could not start.");
          startError.isNotice = payload.severity === "info";
          throw startError;
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
            pendingFiles = Array.isArray(payload.files) ? payload.files : [];
            totalFiles = pendingFiles.length;
            pendingFiles.forEach((fileName) => {
              setFileStatus(activity, fileName, {
                label: fileName,
                tone: "queued",
                detail: "Waiting in queue",
                statusText: "Queued",
              });
            });
            refreshProgress(`Converting ${totalFiles} file(s) to ${outputLabel}...`);
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
            let unprocessed = 0;
            if (payload.success) {
              pendingFiles.forEach((fileName) => {
                if (!completedFiles.has(fileName)) {
                  unprocessed += 1;
                  setFileStatus(activity, fileName, {
                    label: fileName,
                    tone: "error",
                    detail: "Not processed by this run",
                    statusText: "Missed",
                  });
                }
              });
            }
            if (unprocessed > 0) {
              payload.failed += unprocessed;
              payload.message = `${payload.message} ${unprocessed} not processed.`;
            }
            const tone = payload.success && payload.failed === 0 ? "success" : "error";

            updateActivity(activity, {
              detail: payload.message,
              progressPercent: 100,
              tone,
              badgeText: tone === "success" ? "Done" : "Error",
            });

            setButtonBusy(uploadSubmit, false, "Upload");
            setButtonBusy(convertSubmit, false, "Converting...");
            if (formatSelect) {
              formatSelect.disabled = false;
            }

            void refreshPageState().catch((error) => {
              showFlashToast("warning", error.message || "Processing finished, but the file list could not be refreshed.");
            });

            dismissActivity(activity, tone === "success" ? 3200 : 8000);
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
          title: error.isNotice ? "Nothing to convert" : undefined,
          detail: error.message || "Conversion failed. Please try again.",
          progressPercent: 100,
          indeterminate: false,
          tone: error.isNotice ? "success" : "error",
          badgeText: error.isNotice ? "Up to date" : "Error",
        });
        if (error.isNotice) {
          dismissActivity(activity, 3200);
        }
        setButtonBusy(uploadSubmit, false, "Upload");
        setButtonBusy(convertSubmit, false, "Converting...");
        if (formatSelect) {
          formatSelect.disabled = false;
        }
      }
    });
  }

  if (serverFlashes) {
    serverFlashes.querySelectorAll("[data-flash-category]").forEach((flashElement) => {
      const category = flashElement.dataset.flashCategory || "info";
      const message = flashElement.textContent.trim();
      if (message) {
        showFlashToast(category, message);
      }
    });
  }

  updateSummary(fileInput?.files);
});
