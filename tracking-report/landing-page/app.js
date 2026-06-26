const state = {
  data: null,
  tickets: [],
};

const elements = {
  dataMeta: document.getElementById("dataMeta"),
  loadState: document.getElementById("loadState"),
  jsonUpload: document.getElementById("jsonUpload"),
  statusFilter: document.getElementById("statusFilter"),
  ownerFilter: document.getElementById("ownerFilter"),
  resolvedFilter: document.getElementById("resolvedFilter"),
  searchFilter: document.getElementById("searchFilter"),
  clearFilters: document.getElementById("clearFilters"),
  filteredMetrics: document.getElementById("filteredMetrics"),
  overallMetrics: document.getElementById("overallMetrics"),
  statusCountsTable: document.querySelector("#statusCountsTable tbody"),
  movementMeta: document.getElementById("movementMeta"),
  movementTable: document.querySelector("#movementTable tbody"),
  movementDeltaTable: document.querySelector("#movementDeltaTable tbody"),
  ticketCountLabel: document.getElementById("ticketCountLabel"),
  ticketTable: document.querySelector("#ticketTable tbody"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function metricCard(label, value) {
  return `<div class="metric"><div class="label">${escapeHtml(label)}</div><div class="value">${escapeHtml(
    value
  )}</div></div>`;
}

function toNumber(value) {
  if (value === null || value === undefined || value === "") {
    return 0;
  }
  return Number(value) || 0;
}

function buildFilterOptions() {
  const statuses = [...new Set(state.tickets.map((ticket) => ticket.status))].sort((a, b) =>
    a.localeCompare(b)
  );
  const owners = [...new Set(state.tickets.map((ticket) => ticket.owner))].sort((a, b) =>
    a.localeCompare(b)
  );

  elements.statusFilter.innerHTML =
    '<option value="__all__">All statuses</option>' +
    statuses
      .map((status) => `<option value="${escapeHtml(status)}">${escapeHtml(status)}</option>`)
      .join("");
  elements.ownerFilter.innerHTML =
    '<option value="__all__">All owners</option>' +
    owners.map((owner) => `<option value="${escapeHtml(owner)}">${escapeHtml(owner)}</option>`).join("");
}

function currentFilters() {
  return {
    status: elements.statusFilter.value,
    owner: elements.ownerFilter.value,
    resolved: elements.resolvedFilter.value,
    search: elements.searchFilter.value.trim().toLowerCase(),
  };
}

function filterTickets() {
  const filters = currentFilters();
  return state.tickets.filter((ticket) => {
    if (filters.status !== "__all__" && ticket.status !== filters.status) {
      return false;
    }
    if (filters.owner !== "__all__" && ticket.owner !== filters.owner) {
      return false;
    }
    if (filters.resolved === "open" && ticket.is_resolved) {
      return false;
    }
    if (filters.resolved === "resolved" && !ticket.is_resolved) {
      return false;
    }
    if (filters.search) {
      const haystack = [
        ticket.ticket_id,
        ticket.ticket_name,
        ticket.status,
        ticket.owner,
      ]
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(filters.search)) {
        return false;
      }
    }
    return true;
  });
}

function renderOverallMetrics() {
  const metrics = state.data?.metrics || {};
  elements.overallMetrics.innerHTML = [
    metricCard("Total Tickets", toNumber(metrics.total_tickets)),
    metricCard("Open Tickets", toNumber(metrics.open_tickets)),
    metricCard("Resolved Tickets", toNumber(metrics.resolved_tickets)),
    metricCard("Open Missing FedEx Tracking", toNumber(metrics.open_missing_fedex_tracking)),
    metricCard("Open Missing IRS Tracking", toNumber(metrics.open_missing_irs_tracking)),
    metricCard("Open Stale Tickets", toNumber(metrics.open_stale_tickets)),
  ].join("");
}

function renderFilteredMetrics(filteredTickets) {
  const openCount = filteredTickets.filter((ticket) => !ticket.is_resolved).length;
  const resolvedCount = filteredTickets.length - openCount;
  const avgAge =
    filteredTickets.length === 0
      ? 0
      : (
          filteredTickets.reduce((acc, ticket) => acc + toNumber(ticket.age_days), 0) /
          filteredTickets.length
        ).toFixed(1);

  elements.filteredMetrics.innerHTML = [
    metricCard("Filtered Tickets", filteredTickets.length),
    metricCard("Open (Filtered)", openCount),
    metricCard("Resolved (Filtered)", resolvedCount),
    metricCard("Average Age (days)", avgAge),
  ].join("");
}

function renderStatusCounts(filteredTickets) {
  const counts = new Map();
  filteredTickets.forEach((ticket) => {
    counts.set(ticket.status, (counts.get(ticket.status) || 0) + 1);
  });
  const rows = [...counts.entries()].sort((left, right) => right[1] - left[1]);
  elements.statusCountsTable.innerHTML =
    rows.length === 0
      ? "<tr><td colspan='2'>No tickets for current filters.</td></tr>"
      : rows
          .map(
            ([status, count]) =>
              `<tr><td>${escapeHtml(status)}</td><td>${escapeHtml(count)}</td></tr>`
          )
          .join("");
}

function renderMovement() {
  const movement = state.data?.movement || {};
  if (!movement.compared_to_previous_snapshot) {
    elements.movementMeta.textContent = "No previous snapshot supplied, movement tracking is unavailable.";
    elements.movementTable.innerHTML =
      "<tr><td colspan='3'>Provide --previous-snapshot in automation to enable status transitions.</td></tr>";
    elements.movementDeltaTable.innerHTML = "<tr><td colspan='4'>No delta data.</td></tr>";
    return;
  }

  const previousAt = movement.previous_snapshot_generated_at_utc || "unknown";
  elements.movementMeta.textContent = `Compared against snapshot generated at ${previousAt}. New tickets: ${toNumber(
    movement.new_tickets_count
  )}, removed tickets: ${toNumber(movement.removed_tickets_count)}.`;

  const transitionRows = movement.status_transitions || [];
  elements.movementTable.innerHTML =
    transitionRows.length === 0
      ? "<tr><td colspan='3'>No status transitions detected.</td></tr>"
      : transitionRows
          .map(
            (row) =>
              `<tr><td>${escapeHtml(row.from_status)}</td><td>${escapeHtml(row.to_status)}</td><td>${escapeHtml(
                row.count
              )}</td></tr>`
          )
          .join("");

  const deltaRows = movement.status_count_delta || [];
  elements.movementDeltaTable.innerHTML =
    deltaRows.length === 0
      ? "<tr><td colspan='4'>No status deltas detected.</td></tr>"
      : deltaRows
          .map((row) => {
            const delta = toNumber(row.delta);
            const renderedDelta = delta > 0 ? `+${delta}` : String(delta);
            return `<tr><td>${escapeHtml(row.status)}</td><td>${escapeHtml(
              row.previous_count
            )}</td><td>${escapeHtml(row.current_count)}</td><td>${escapeHtml(renderedDelta)}</td></tr>`;
          })
          .join("");
}

function renderTickets(filteredTickets) {
  elements.ticketCountLabel.textContent = String(filteredTickets.length);
  const maxRows = 300;
  const displayed = filteredTickets.slice(0, maxRows);

  elements.ticketTable.innerHTML =
    displayed.length === 0
      ? "<tr><td colspan='6'>No tickets for current filters.</td></tr>"
      : displayed
          .map((ticket) => {
            const resolved = ticket.is_resolved ? "Yes" : "No";
            const age = ticket.age_days === null || ticket.age_days === undefined ? "" : ticket.age_days;
            return `<tr>
              <td>${escapeHtml(ticket.ticket_id)}</td>
              <td>${escapeHtml(ticket.ticket_name)}</td>
              <td>${escapeHtml(ticket.status)}</td>
              <td>${escapeHtml(ticket.owner)}</td>
              <td>${escapeHtml(age)}</td>
              <td>${resolved}</td>
            </tr>`;
          })
          .join("");
}

function renderDashboard() {
  if (!state.data) {
    return;
  }
  const filteredTickets = filterTickets();
  renderOverallMetrics();
  renderFilteredMetrics(filteredTickets);
  renderStatusCounts(filteredTickets);
  renderMovement();
  renderTickets(filteredTickets);
}

function applyData(data, sourceLabel) {
  state.data = data;
  state.tickets = Array.isArray(data.tickets) ? data.tickets : [];

  buildFilterOptions();
  renderDashboard();

  elements.dataMeta.textContent = `Snapshot generated at ${data.generated_at_utc || "unknown"} from ${
    data.source_csv || "unknown source"
  }`;
  elements.loadState.textContent = `Loaded ${state.tickets.length} tickets from ${sourceLabel}.`;
}

async function loadDefaultData() {
  try {
    const response = await fetch("./data/landing_page_data.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    applyData(data, "default data path");
  } catch (error) {
    elements.loadState.textContent =
      "Default data not found yet. Upload landing_page_data.json with the file picker.";
    elements.dataMeta.textContent = "Dashboard data not loaded.";
  }
}

elements.jsonUpload.addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }
  try {
    const payload = await file.text();
    const data = JSON.parse(payload);
    applyData(data, file.name);
  } catch (error) {
    elements.loadState.textContent = "Unable to parse selected JSON file.";
  }
});

elements.clearFilters.addEventListener("click", () => {
  elements.statusFilter.value = "__all__";
  elements.ownerFilter.value = "__all__";
  elements.resolvedFilter.value = "all";
  elements.searchFilter.value = "";
  renderDashboard();
});

for (const input of [elements.statusFilter, elements.ownerFilter, elements.resolvedFilter, elements.searchFilter]) {
  input.addEventListener("input", renderDashboard);
  input.addEventListener("change", renderDashboard);
}

loadDefaultData();
