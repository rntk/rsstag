(function () {
  function getInitialPayload() {
    var node = document.getElementById("anthology-detail-data");
    if (!node) {
      return null;
    }

    try {
      return JSON.parse(node.textContent || "{}");
    } catch (error) {
      return null;
    }
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatTimestamp(timestamp) {
    var numericTimestamp = Number(timestamp || 0);
    if (!numericTimestamp) {
      return "N/A";
    }

    try {
      return new Date(numericTimestamp * 1000).toLocaleString();
    } catch (error) {
      return "N/A";
    }
  }

  function stringifyValue(value) {
    if (value === null || value === undefined || value === "") {
      return "—";
    }
    if (typeof value === "string") {
      return value;
    }
    try {
      return JSON.stringify(value, null, 2);
    } catch (error) {
      return String(value);
    }
  }

  function shortenText(value, maxLength) {
    var text = String(value || "").trim();
    if (text.length <= maxLength) {
      return text;
    }

    return text.slice(0, maxLength - 1) + "…";
  }

  function pluralize(count, singular, plural) {
    return count === 1 ? singular : plural;
  }

  function renderSourceRefs(sourceRefs) {
    if (!Array.isArray(sourceRefs) || sourceRefs.length === 0) {
      return '<p class="anthology-empty-state">No source references captured yet.</p>';
    }

    return (
      '<ul class="anthology-source-list">' +
      sourceRefs
        .map(function (sourceRef) {
          var item = sourceRef && typeof sourceRef === "object" ? sourceRef : {};
          var label =
            item.topic_path ||
            item.title ||
            item.label ||
            item.post_id ||
            item.url ||
            "Source reference";
          var postId = item.post_id
            ? '<span class="anthology-source-meta">post ' +
              escapeHtml(item.post_id) +
              "</span>"
            : "";
          var sentenceMeta =
            Array.isArray(item.sentence_indices) && item.sentence_indices.length > 0
              ? '<span class="anthology-source-meta">sentences ' +
                escapeHtml(item.sentence_indices.join(", ")) +
                "</span>"
              : "";
          var readState = item.read_state || {};
          var readMeta =
            typeof readState.total_sentences === "number"
              ? '<span class="anthology-source-meta">' +
                escapeHtml(readState.unread_sentences || 0) +
                " unread / " +
                escapeHtml(readState.total_sentences || 0) +
                " total</span>"
              : "";
          var action =
            Array.isArray(item.sentence_indices) && item.sentence_indices.length > 0
              ? '<button type="button" class="anthology-inline-action anthology-read-action" data-target-kind="sentences" data-post-id="' +
                escapeHtml(item.post_id || "") +
                '" data-sentence-indices="' +
                escapeHtml(JSON.stringify(item.sentence_indices)) +
                '" data-readed="' +
                (readState.all_read ? "false" : "true") +
                '">' +
                (readState.all_read ? "Mark unread" : "Mark read") +
                "</button>"
              : "";

          return (
            '<li class="anthology-source-item">' +
            '<span class="anthology-source-label">' +
            escapeHtml(label) +
            "</span>" +
            postId +
            sentenceMeta +
            readMeta +
            action +
            "</li>"
          );
        })
        .join("") +
      "</ul>"
    );
  }

  function renderTreeNode(node, level) {
    if (!node || typeof node !== "object") {
      return '<p class="anthology-empty-state">No hierarchy has been generated yet.</p>';
    }

    var children = Array.isArray(node.sub_anthologies) ? node.sub_anthologies : [];
    var sourceRefs = Array.isArray(node.source_refs) ? node.source_refs : [];
    var readState = node.read_state || {};
    var title = escapeHtml(node.title || "Section " + (level + 1));
    var summary = String(node.summary || "").trim();
    var summaryText = summary
      ? '<p class="anthology-tree-body">' + escapeHtml(summary) + "</p>"
      : "";
    var meta =
      '<div class="anthology-tree-meta">' +
      "<span>" +
      sourceRefs.length +
      " " +
      pluralize(sourceRefs.length, "source", "sources") +
      "</span>" +
      (typeof readState.total_sentences === "number"
        ? "<span>" +
          escapeHtml(readState.unread_sentences || 0) +
          " unread / " +
          escapeHtml(readState.total_sentences || 0) +
          " total</span>"
        : "") +
      "<span>depth " +
      escapeHtml(level + 1) +
      "</span>" +
      "</div>";
    var readAction =
      '<div class="anthology-node-actions">' +
      '<button type="button" class="anthology-inline-action anthology-read-action" data-target-kind="' +
      (level === 0 ? "anthology" : "node") +
      '"' +
      (level === 0 ? "" : ' data-node-id="' + escapeHtml(node.node_id || "") + '"') +
      ' data-readed="' +
      (readState.all_read ? "false" : "true") +
      '">' +
      (readState.all_read ? "Mark unread" : "Mark read") +
      "</button>" +
      "</div>";
    var refsMarkup = sourceRefs.length > 0 ? renderSourceRefs(sourceRefs) : "";

    if (children.length > 0) {
      return (
        '<div class="anthology-tree-node level-' +
        escapeHtml(level) +
        '">' +
        '<details class="anthology-tree-details"' +
        (level < 1 ? " open" : "") +
        ">" +
        '<summary class="anthology-tree-summary">' +
        '<span class="anthology-tree-summary-main">' +
        '<span class="anthology-tree-title">' +
        title +
        "</span>" +
        (summary
          ? '<span class="anthology-tree-summary-text">' +
            escapeHtml(shortenText(summary, 160)) +
            "</span>"
          : "") +
        "</span>" +
        '<span class="anthology-tree-count">' +
        children.length +
        " " +
        pluralize(children.length, "section", "sections") +
        "</span>" +
        "</summary>" +
        '<div class="anthology-tree-content">' +
        summaryText +
        meta +
        readAction +
        refsMarkup +
        '<div class="anthology-tree-children">' +
        children
          .map(function (child) {
            return renderTreeNode(child, level + 1);
          })
          .join("") +
        "</div>" +
        "</div>" +
        "</details>" +
        "</div>"
      );
    }

    return (
      '<div class="anthology-tree-node level-' +
      escapeHtml(level) +
      '">' +
      '<div class="anthology-tree-leaf">' +
      '<div class="anthology-tree-leaf-title">' +
      title +
      "</div>" +
      summaryText +
      meta +
      readAction +
      refsMarkup +
      "</div>" +
      "</div>"
    );
  }

  function renderRunSummary(run) {
    if (!run || typeof run !== "object") {
      return '<p class="anthology-empty-state">No run has started yet.</p>';
    }

    return (
      '<div class="anthology-run-meta">' +
      "<span>run " +
      escapeHtml(run._id || "—") +
      "</span>" +
      "<span>status " +
      escapeHtml(run.status || "unknown") +
      "</span>" +
      "<span>started " +
      escapeHtml(formatTimestamp(run.started_at)) +
      "</span>" +
      "<span>" +
      (run.finished_at
        ? "finished " + escapeHtml(formatTimestamp(run.finished_at))
        : "still running") +
      "</span>" +
      "</div>" +
      (run.error
        ? '<p class="anthology-run-error">' + escapeHtml(run.error) + "</p>"
        : "")
    );
  }

  function renderLogEntries(items, emptyText) {
    if (!Array.isArray(items) || items.length === 0) {
      return '<p class="anthology-empty-state">' + escapeHtml(emptyText) + "</p>";
    }

    return items
      .map(function (item) {
        var role = item && item.role ? item.role : "";
        var header = role
          ? '<div class="anthology-log-entry-header">' + escapeHtml(role) + "</div>"
          : "";

        return (
          '<div class="anthology-log-entry">' +
          header +
          '<pre class="anthology-log-pre">' +
          escapeHtml(stringifyValue(item && Object.prototype.hasOwnProperty.call(item, "content") ? item.content : item)) +
          "</pre>" +
          "</div>"
        );
      })
      .join("");
  }

  function renderTurns(run) {
    var turns = run && Array.isArray(run.turns) ? run.turns : [];
    if (turns.length === 0) {
      return '<p class="anthology-empty-state">Logs will appear here when a run is available.</p>';
    }

    return turns
      .map(function (turn, index) {
        var messages = Array.isArray(turn.messages) ? turn.messages : [];
        var toolCalls = Array.isArray(turn.tool_calls) ? turn.tool_calls : [];
        var toolResults = Array.isArray(turn.tool_results) ? turn.tool_results : [];

        return (
          '<details class="anthology-log-turn"' +
          (index === turns.length - 1 ? " open" : "") +
          ">" +
          '<summary class="anthology-log-turn-summary">' +
          "<span>Turn " +
          escapeHtml(turn.turn || index + 1) +
          "</span>" +
          "<span>" +
          messages.length +
          " messages</span>" +
          "<span>" +
          toolCalls.length +
          " tool calls</span>" +
          "<span>" +
          toolResults.length +
          " tool results</span>" +
          "</summary>" +
          '<div class="anthology-log-grid">' +
          '<section class="anthology-log-block">' +
          "<h3>Messages</h3>" +
          renderLogEntries(messages, "No messages.") +
          "</section>" +
          '<section class="anthology-log-block">' +
          "<h3>Tool calls</h3>" +
          renderLogEntries(toolCalls, "No tool calls.") +
          "</section>" +
          '<section class="anthology-log-block">' +
          "<h3>Tool results</h3>" +
          renderLogEntries(toolResults, "No tool results.") +
          "</section>" +
          "</div>" +
          "</details>"
        );
      })
      .join("");
  }

  function setText(id, value) {
    var node = document.getElementById(id);
    if (node) {
      node.textContent = value;
    }
  }

  function updateStatusClass(headerNode, status) {
    var knownStatuses = ["pending", "processing", "done", "failed"];
    knownStatuses.forEach(function (knownStatus) {
      headerNode.classList.remove("anthology-status-" + knownStatus);
    });
    headerNode.classList.add("anthology-status-" + status);
  }

  var pageRoot = document.getElementById("anthology-detail-page");
  var initialPayload = getInitialPayload();
  var currentPayload = initialPayload;
  var pollingTimer = null;

  if (!pageRoot || !initialPayload) {
    return;
  }

  function isProcessing(payload) {
    var status = payload && payload.status ? String(payload.status) : "";
    return status === "pending" || status === "processing";
  }

  function updatePlaceholderButtons(retryUrl, exportUrl) {
    var retryButton = document.getElementById("anthology-retry-button");
    var exportButton = document.getElementById("anthology-export-button");
    if (retryButton) {
      retryButton.dataset.apiUrl = retryUrl;
    }
    if (exportButton) {
      exportButton.dataset.apiUrl = exportUrl;
    }
  }

  async function postJson(url, payload) {
    var response = await fetch(url, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
    var data = await response.json();
    if (!response.ok || data.error) {
      throw new Error((data && data.error) || "Request failed");
    }
    return data;
  }

  function renderPayload(payload) {
    var headerNode = document.getElementById("anthology-detail-header");
    var staleBadgeNode = document.getElementById("anthology-stale-badge");
    var summaryNode = document.getElementById("anthology-summary");
    var scopeNode = document.getElementById("anthology-scope-json");
    var hierarchyNode = document.getElementById("anthology-hierarchy-tree");
    var sourceRefsNode = document.getElementById("anthology-source-refs");
    var runSummaryNode = document.getElementById("anthology-run-summary");
    var logViewerNode = document.getElementById("anthology-log-viewer");
    var processingNoteNode = document.getElementById("anthology-processing-note");
    var refreshNode = document.getElementById("anthology-last-refresh");

    if (headerNode) {
      updateStatusClass(headerNode, payload.status || "pending");
    }

    setText("anthology-title", payload.title || payload.seed_value || "Anthology");
    setText("anthology-status-badge", payload.status || "pending");
    setText("anthology-status", payload.status || "pending");
    setText("anthology-seed-value", payload.seed_value || "");
    setText("anthology-seed-type", payload.seed_type || "");
    setText("anthology-created-at", formatTimestamp(payload.created_at));
    setText("anthology-updated-at", formatTimestamp(payload.updated_at));
    setText("anthology-current-run", payload.current_run_id || "—");
    setText(
      "anthology-source-snapshot-updated",
      payload.source_snapshot && payload.source_snapshot.post_grouping_updated_at
        ? formatTimestamp(payload.source_snapshot.post_grouping_updated_at)
        : "N/A"
    );
    setText(
      "anthology-source-snapshot-count",
      payload.source_snapshot &&
        Array.isArray(payload.source_snapshot.post_grouping_doc_ids)
        ? String(payload.source_snapshot.post_grouping_doc_ids.length)
        : "0"
    );

    if (summaryNode) {
      summaryNode.textContent =
        payload.result && payload.result.summary
          ? payload.result.summary
          : "Anthology output is still being prepared.";
    }

    if (scopeNode) {
      scopeNode.textContent = stringifyValue(payload.scope || {});
    }

    if (hierarchyNode) {
      hierarchyNode.innerHTML =
        payload.result && typeof payload.result === "object"
          ? renderTreeNode(payload.result, 0)
          : '<p class="anthology-empty-state">No hierarchy has been generated yet.</p>';
    }

    if (sourceRefsNode) {
      sourceRefsNode.innerHTML = renderSourceRefs(
        payload.result && Array.isArray(payload.result.source_refs)
          ? payload.result.source_refs
          : []
      );
    }

    if (runSummaryNode) {
      runSummaryNode.innerHTML = renderRunSummary(payload.latest_run);
    }

    if (logViewerNode) {
      logViewerNode.innerHTML = renderTurns(payload.latest_run);
    }

    if (staleBadgeNode) {
      staleBadgeNode.classList.toggle("hide", !payload.stale);
    }

    if (processingNoteNode) {
      processingNoteNode.textContent = isProcessing(payload)
        ? "Polling detail API while the anthology is processing."
        : "Anthology is not actively processing.";
    }

    if (refreshNode) {
      refreshNode.textContent = payload.updated_at
        ? "Updated " + formatTimestamp(payload.updated_at)
        : "Updated N/A";
    }

    updatePlaceholderButtons(
      "/api/anthologies/" + escapeURIComponent(payload.id) + "/retry",
      "/api/anthologies/" + escapeURIComponent(payload.id) + "/export"
    );

    document.title = (payload.title || "Anthology") + " | Anthology";
  }

  function escapeURIComponent(value) {
    return encodeURIComponent(String(value || ""));
  }

  async function refreshPayload() {
    var apiUrl = pageRoot.dataset.apiUrl;
    if (!apiUrl) {
      return;
    }

    try {
      var response = await fetch(apiUrl, {
        headers: { Accept: "application/json" },
        cache: "no-store"
      });
      if (!response.ok) {
        throw new Error("Failed to refresh anthology detail");
      }

      var payload = await response.json();
      currentPayload = payload && payload.data ? payload.data : payload;
      renderPayload(currentPayload);

      if (!isProcessing(currentPayload)) {
        stopPolling();
      }
    } catch (error) {
      var actionNoteNode = document.getElementById("anthology-action-note");
      if (actionNoteNode) {
        actionNoteNode.textContent = "Unable to refresh anthology data right now.";
      }
    }
  }

  function stopPolling() {
    if (pollingTimer) {
      window.clearInterval(pollingTimer);
      pollingTimer = null;
    }
  }

  function startPolling() {
    var interval = Number(pageRoot.dataset.pollIntervalMs || 5000);
    if (!isProcessing(currentPayload) || pollingTimer) {
      return;
    }

    pollingTimer = window.setInterval(function () {
      refreshPayload();
    }, interval);
  }

  document.addEventListener("click", function (event) {
    var actionNoteNode = document.getElementById("anthology-action-note");
    var target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    if (target.classList.contains("anthology-placeholder-action")) {
      var apiUrl = target.dataset.apiUrl || "";
      if (!apiUrl) {
        return;
      }
      if (target.id === "anthology-export-button") {
        window.location.href = apiUrl + "?format=json";
        return;
      }
      if (target.id === "anthology-retry-button") {
        if (actionNoteNode) {
          actionNoteNode.textContent = "Retrying anthology...";
        }
        postJson(apiUrl, {})
          .then(function (payload) {
            currentPayload = payload && payload.data ? payload.data : currentPayload;
            renderPayload(currentPayload);
            startPolling();
            if (actionNoteNode) {
              actionNoteNode.textContent = "Anthology retry queued.";
            }
          })
          .catch(function (error) {
            if (actionNoteNode) {
              actionNoteNode.textContent = error.message;
            }
          });
      }
      return;
    }

    if (!target.classList.contains("anthology-read-action")) {
      return;
    }

    if (!currentPayload || !currentPayload.id) {
      return;
    }

    var requestPayload = {
      readed: String(target.dataset.readed || "true") === "true",
      target: {
        kind: target.dataset.targetKind || "anthology"
      }
    };
    if (target.dataset.nodeId) {
      requestPayload.target.node_id = target.dataset.nodeId;
    }
    if (target.dataset.postId) {
      requestPayload.target.post_id = target.dataset.postId;
    }
    if (target.dataset.sentenceIndices) {
      try {
        requestPayload.target.sentence_indices = JSON.parse(target.dataset.sentenceIndices);
      } catch (_error) {
        requestPayload.target.sentence_indices = [];
      }
    }
    if (actionNoteNode) {
      actionNoteNode.textContent = "Updating read state...";
    }
    postJson(
      "/api/anthologies/" + escapeURIComponent(currentPayload.id) + "/read",
      requestPayload
    )
      .then(function (payload) {
        currentPayload = payload && payload.data ? payload.data : currentPayload;
        renderPayload(currentPayload);
        if (actionNoteNode) {
          actionNoteNode.textContent = "Read state updated.";
        }
      })
      .catch(function (error) {
        if (actionNoteNode) {
          actionNoteNode.textContent = error.message;
        }
      });
  });

  document.addEventListener("visibilitychange", function () {
    if (!document.hidden && isProcessing(currentPayload)) {
      refreshPayload();
    }
  });

  renderPayload(currentPayload);
  startPolling();
})();
