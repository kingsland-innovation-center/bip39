(function () {
    var PAGE_SIZE = 50;
    var rows = [];
    var filteredRows = [];
    var currentPage = 1;

    var csvFileInput = document.getElementById("csvFile");
    var loadStatus = document.getElementById("loadStatus");
    var searchInput = document.getElementById("searchInput");
    var ownerFilter = document.getElementById("ownerFilter");
    var statusFilter = document.getElementById("statusFilter");
    var quarterFilter = document.getElementById("quarterFilter");
    var sortBy = document.getElementById("sortBy");
    var sortDirection = document.getElementById("sortDirection");
    var tableBody = document.getElementById("tableBody");
    var resultsSummary = document.getElementById("resultsSummary");
    var prevPageButton = document.getElementById("prevPage");
    var nextPageButton = document.getElementById("nextPage");
    var pageInfo = document.getElementById("pageInfo");
    var ownerSummary = document.getElementById("ownerSummary");

    var totalTickets = document.getElementById("totalTickets");
    var newTickets = document.getElementById("newTickets");
    var inProgressTickets = document.getElementById("inProgressTickets");
    var resolvedTickets = document.getElementById("resolvedTickets");

    csvFileInput.addEventListener("change", handleFileChange);
    searchInput.addEventListener("input", applyFilters);
    ownerFilter.addEventListener("change", applyFilters);
    statusFilter.addEventListener("change", applyFilters);
    quarterFilter.addEventListener("change", applyFilters);
    sortBy.addEventListener("change", applyFilters);
    sortDirection.addEventListener("change", applyFilters);
    prevPageButton.addEventListener("click", goToPreviousPage);
    nextPageButton.addEventListener("click", goToNextPage);

    function handleFileChange(event) {
        var selectedFile = event.target.files && event.target.files[0];
        if (!selectedFile) {
            return;
        }

        var reader = new FileReader();
        reader.onload = function () {
            try {
                var text = String(reader.result || "");
                rows = convertToRecords(parseCsv(text));
                currentPage = 1;
                loadStatus.textContent = "Loaded " + selectedFile.name + " (" + rows.length + " tickets)";
                buildFilterOptions();
                applyFilters();
            }
            catch (error) {
                rows = [];
                filteredRows = [];
                renderAll();
                loadStatus.textContent = "Could not parse file. Please verify the CSV format.";
            }
        };
        reader.readAsText(selectedFile);
    }

    function parseCsv(rawText) {
        var normalizedText = rawText.replace(/\r\n/g, "\n");
        var records = [];
        var row = [];
        var value = "";
        var inQuotes = false;
        var i;

        for (i = 0; i < normalizedText.length; i += 1) {
            var char = normalizedText[i];
            var nextChar = normalizedText[i + 1];

            if (char === "\"") {
                if (inQuotes && nextChar === "\"") {
                    value += "\"";
                    i += 1;
                }
                else {
                    inQuotes = !inQuotes;
                }
                continue;
            }

            if (char === "," && !inQuotes) {
                row.push(value);
                value = "";
                continue;
            }

            if (char === "\n" && !inQuotes) {
                row.push(value);
                value = "";
                records.push(row);
                row = [];
                continue;
            }

            value += char;
        }

        if (value.length > 0 || row.length > 0) {
            row.push(value);
            records.push(row);
        }

        return records;
    }

    function convertToRecords(parsedRows) {
        if (!parsedRows.length) {
            return [];
        }

        var headers = parsedRows[0];
        var headerMap = {};
        var index;
        for (index = 0; index < headers.length; index += 1) {
            headerMap[headers[index]] = index;
        }

        return parsedRows.slice(1).filter(function (row) {
            return row.length > 1;
        }).map(function (row) {
            return {
                ticketId: getCell(row, headerMap, "Ticket ID"),
                ticketName: getCell(row, headerMap, "Ticket name"),
                status: getCell(row, headerMap, "Ticket status"),
                owner: getCell(row, headerMap, "Ticket owner"),
                quarter: getCell(row, headerMap, "Related Quarter"),
                dateOfNotification: getCell(row, headerMap, "Date of Notification"),
                dueDate: getCell(row, headerMap, "Due Date of Issue Notification"),
                createDate: getCell(row, headerMap, "Create date"),
                lastModifiedDate: getCell(row, headerMap, "Last modified date"),
                associatedDeal: getCell(row, headerMap, "Associated Deal"),
                dealClientId: getCell(row, headerMap, "Deal Client ID")
            };
        });
    }

    function getCell(row, headerMap, columnName) {
        var columnIndex = headerMap[columnName];
        if (typeof columnIndex !== "number") {
            return "";
        }
        return (row[columnIndex] || "").trim();
    }

    function buildFilterOptions() {
        populateSelect(ownerFilter, uniqueValues(rows, "owner"), "All owners");
        populateSelect(statusFilter, uniqueValues(rows, "status"), "All statuses");
        populateSelect(quarterFilter, uniqueValues(rows, "quarter"), "All quarters");
    }

    function populateSelect(selectElement, values, defaultLabel) {
        var currentValue = selectElement.value;
        selectElement.innerHTML = "";

        var defaultOption = document.createElement("option");
        defaultOption.value = "";
        defaultOption.textContent = defaultLabel;
        selectElement.appendChild(defaultOption);

        values.forEach(function (value) {
            var option = document.createElement("option");
            option.value = value;
            option.textContent = value;
            selectElement.appendChild(option);
        });

        if (values.indexOf(currentValue) >= 0) {
            selectElement.value = currentValue;
        }
    }

    function uniqueValues(collection, key) {
        var uniq = {};
        collection.forEach(function (item) {
            var value = item[key];
            if (value) {
                uniq[value] = true;
            }
        });
        return Object.keys(uniq).sort(function (a, b) {
            return a.localeCompare(b);
        });
    }

    function applyFilters() {
        var query = searchInput.value.toLowerCase().trim();
        var owner = ownerFilter.value;
        var status = statusFilter.value;
        var quarter = quarterFilter.value;

        filteredRows = rows.filter(function (item) {
            var matchesQuery = !query || [
                item.ticketId,
                item.ticketName,
                item.associatedDeal,
                item.dealClientId
            ].join(" ").toLowerCase().indexOf(query) >= 0;

            var matchesOwner = !owner || item.owner === owner;
            var matchesStatus = !status || item.status === status;
            var matchesQuarter = !quarter || item.quarter === quarter;

            return matchesQuery && matchesOwner && matchesStatus && matchesQuarter;
        });

        sortRows(filteredRows);
        currentPage = 1;
        renderAll();
    }

    function sortRows(collection) {
        var activeSortBy = sortBy.value;
        var direction = sortDirection.value === "asc" ? 1 : -1;

        collection.sort(function (a, b) {
            var first;
            var second;

            if (activeSortBy === "ticketName") {
                first = a.ticketName.toLowerCase();
                second = b.ticketName.toLowerCase();
                return first.localeCompare(second) * direction;
            }

            if (activeSortBy === "modified") {
                first = parseDate(a.lastModifiedDate);
                second = parseDate(b.lastModifiedDate);
                return compareDates(first, second, direction);
            }

            if (activeSortBy === "due") {
                first = parseDate(a.dueDate);
                second = parseDate(b.dueDate);
                return compareDates(first, second, direction);
            }

            first = parseDate(a.createDate);
            second = parseDate(b.createDate);
            return compareDates(first, second, direction);
        });
    }

    function compareDates(first, second, direction) {
        if (first === second) {
            return 0;
        }
        if (first === null) {
            return 1;
        }
        if (second === null) {
            return -1;
        }
        return (first - second) * direction;
    }

    function parseDate(value) {
        if (!value) {
            return null;
        }
        var candidate = value.replace(" ", "T");
        var parsed = Date.parse(candidate);
        if (isNaN(parsed)) {
            return null;
        }
        return parsed;
    }

    function renderAll() {
        renderSummaryCards();
        renderOwnerSummary();
        renderTable();
        renderPagination();
        renderResultsSummary();
    }

    function renderSummaryCards() {
        var summary = summarizeByCategory(filteredRows.length ? filteredRows : rows);
        totalTickets.textContent = String(summary.total);
        newTickets.textContent = String(summary.newCount);
        inProgressTickets.textContent = String(summary.inProgressCount);
        resolvedTickets.textContent = String(summary.resolvedCount);
    }

    function summarizeByCategory(collection) {
        var summary = {
            total: collection.length,
            newCount: 0,
            inProgressCount: 0,
            resolvedCount: 0
        };

        collection.forEach(function (item) {
            var category = getStatusCategory(item.status);
            if (category === "new") {
                summary.newCount += 1;
            }
            else if (category === "in-progress") {
                summary.inProgressCount += 1;
            }
            else if (category === "resolved") {
                summary.resolvedCount += 1;
            }
        });

        return summary;
    }

    function renderOwnerSummary() {
        if (!rows.length) {
            ownerSummary.innerHTML = "<p class=\"results-summary\">No data loaded.</p>";
            return;
        }

        var ownerCounts = {};
        filteredRows.forEach(function (item) {
            var key = item.owner || "Unassigned";
            ownerCounts[key] = (ownerCounts[key] || 0) + 1;
        });

        var sortedOwners = Object.keys(ownerCounts).sort(function (a, b) {
            return ownerCounts[b] - ownerCounts[a];
        }).slice(0, 7);

        if (!sortedOwners.length) {
            ownerSummary.innerHTML = "<p class=\"results-summary\">No owners match the selected filters.</p>";
            return;
        }

        ownerSummary.innerHTML = sortedOwners.map(function (ownerName) {
            return (
                "<div class=\"owner-row\">" +
                "<span class=\"owner-name\">" + escapeHtml(ownerName) + "</span>" +
                "<span class=\"owner-count\">" + ownerCounts[ownerName] + "</span>" +
                "</div>"
            );
        }).join("");
    }

    function renderTable() {
        if (!rows.length) {
            tableBody.innerHTML = "<tr><td colspan=\"9\" class=\"empty-table\">Upload a CSV file to populate this table.</td></tr>";
            return;
        }

        if (!filteredRows.length) {
            tableBody.innerHTML = "<tr><td colspan=\"9\" class=\"empty-table\">No rows match your filters.</td></tr>";
            return;
        }

        var pageCount = getPageCount();
        if (currentPage > pageCount) {
            currentPage = pageCount;
        }

        var startIndex = (currentPage - 1) * PAGE_SIZE;
        var endIndex = startIndex + PAGE_SIZE;
        var pageRows = filteredRows.slice(startIndex, endIndex);

        tableBody.innerHTML = pageRows.map(function (item) {
            var statusCategory = getStatusCategory(item.status);
            var statusValue = item.status || "Unknown";

            return (
                "<tr>" +
                "<td>" + escapeHtml(item.ticketId || "-") + "</td>" +
                "<td>" + escapeHtml(item.ticketName || "-") + "</td>" +
                "<td><span class=\"status-pill " + statusCategory + "\">" + escapeHtml(statusValue) + "</span></td>" +
                "<td>" + escapeHtml(item.owner || "-") + "</td>" +
                "<td>" + escapeHtml(item.quarter || "-") + "</td>" +
                "<td>" + escapeHtml(item.dateOfNotification || "-") + "</td>" +
                "<td>" + escapeHtml(item.dueDate || "-") + "</td>" +
                "<td>" + escapeHtml(item.createDate || "-") + "</td>" +
                "<td>" + escapeHtml(item.lastModifiedDate || "-") + "</td>" +
                "</tr>"
            );
        }).join("");
    }

    function renderPagination() {
        var pageCount = getPageCount();
        pageInfo.textContent = "Page " + pageCountSafe(currentPage, pageCount) + " of " + pageCount;
        prevPageButton.disabled = currentPage <= 1;
        nextPageButton.disabled = currentPage >= pageCount;
    }

    function pageCountSafe(page, count) {
        if (!count) {
            return 1;
        }
        if (page < 1) {
            return 1;
        }
        if (page > count) {
            return count;
        }
        return page;
    }

    function getPageCount() {
        var count = Math.ceil(filteredRows.length / PAGE_SIZE);
        return Math.max(count, 1);
    }

    function renderResultsSummary() {
        var shownStart = filteredRows.length ? ((currentPage - 1) * PAGE_SIZE) + 1 : 0;
        var shownEnd = Math.min(currentPage * PAGE_SIZE, filteredRows.length);
        resultsSummary.textContent = shownStart + "-" + shownEnd + " of " + filteredRows.length + " filtered tickets";
    }

    function goToPreviousPage() {
        if (currentPage > 1) {
            currentPage -= 1;
            renderAll();
        }
    }

    function goToNextPage() {
        var pageCount = getPageCount();
        if (currentPage < pageCount) {
            currentPage += 1;
            renderAll();
        }
    }

    function getStatusCategory(status) {
        var normalized = (status || "").toLowerCase();
        if (normalized.indexOf("resolved") >= 0) {
            return "resolved";
        }
        if (
            normalized.indexOf("in progress") >= 0 ||
            normalized.indexOf("assigned") >= 0 ||
            normalized.indexOf("forwarded") >= 0
        ) {
            return "in-progress";
        }
        if (normalized.indexOf("waiting") >= 0) {
            return "waiting";
        }
        if (normalized.indexOf("new") >= 0) {
            return "new";
        }
        return "other";
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    renderAll();
}());
