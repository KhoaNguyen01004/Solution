let currentEditTripId = null;

function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#39;"
    })[char]));
}

async function loadTrips() {
    try {
        const res = await fetch("/api/trip-history");
        const data = await res.json();
        if (Array.isArray(data)) {
            renderTrips(data);
        } else if (data.success && Array.isArray(data.trips)) {
            renderTrips(data.trips);
        } else {
            showToast(data.message || "Failed to load trips", "error");
        }
    } catch (err) {
        console.error(err);
        showToast("Failed to load trips", "error");
    }
}

function renderTrips(trips) {
    const tbody = document.getElementById("tripsTableBody");
    tbody.innerHTML = "";

    if (trips.length === 0) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td colspan="10" class="empty-state">
                <h3 style="margin: 0 0 8px 0; font-size: 18px;">No trips yet</h3>
                <p style="margin: 0;">Create your first trip in Manage Trips</p>
            </td>
        `;
        tbody.appendChild(tr);
        return;
    }

    trips.forEach(trip => {
        // Compute duration
        let durationText = 'N/A';
        if (trip.created_at && trip.completed_at) {
            const start = new Date(trip.created_at + 'Z');
            const end = new Date(trip.completed_at + 'Z');
            const elapsed = Math.floor((end - start) / 1000);
            if (elapsed > 0) {
                const mins = Math.floor(elapsed / 60);
                const hrs = Math.floor(mins / 60);
                durationText = hrs > 0 ? `${hrs}h ${mins % 60}m` : `${mins}m`;
            }
        }
        
        const driverName = trip.driver_name || 'N/A';
        
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${escapeHtml(trip.customer_name || "N/A")}</td>
            <td>${escapeHtml(trip.vehicle_name || "N/A")}</td>
            <td>${escapeHtml(driverName)}</td>
            <td>${escapeHtml(trip.pickup_name || "N/A")}</td>
            <td>${escapeHtml(trip.destination_name || "N/A")}</td>
            <td>${escapeHtml(durationText)}</td>
            <td>
                <span class="status-badge ${escapeHtml(trip.status || "queued")}">
                    ${escapeHtml(trip.status || "Queued").charAt(0).toUpperCase() + escapeHtml(trip.status || "Queued").slice(1)}
                </span>
            </td>
            <td>${escapeHtml(trip.queue_order || 0)}</td>
            <td>${escapeHtml(trip.created_at || "N/A")}</td>
            <td class="actions">
                <button class="btn-secondary" data-action="edit" data-id="${trip.id}">Edit</button>
                <button class="btn-danger" data-action="delete" data-id="${trip.id}" data-vehicle-id="${escapeHtml(trip.vehicle_id)}">Delete</button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    // Add event listeners
    tbody.querySelectorAll("[data-action='edit']").forEach(btn => {
        btn.addEventListener("click", () => openEditModal(parseInt(btn.dataset.id), trips));
    });

    tbody.querySelectorAll("[data-action='delete']").forEach(btn => {
        btn.addEventListener("click", () => deleteTrip(parseInt(btn.dataset.id), btn.dataset.vehicleId));
    });
}

function openEditModal(tripId, trips) {
    const trip = trips.find(t => t.id === tripId);
    if (!trip) return;

    currentEditTripId = tripId;
    document.getElementById("customerName").value = trip.customer_name || "";
    document.getElementById("vehicleName").value = trip.vehicle_name || "";
    document.getElementById("pickupName").value = trip.pickup_name || "";
    document.getElementById("destinationName").value = trip.destination_name || "";
    document.getElementById("tripStatus").value = trip.status || "queued";
    document.getElementById("queueOrder").value = trip.queue_order || 0;

    document.getElementById("editTripModal").classList.remove("hidden");
}

function closeEditModal() {
    document.getElementById("editTripModal").classList.add("hidden");
    currentEditTripId = null;
}

async function saveTrip() {
    if (!currentEditTripId) return;

    try {
        const res = await fetch("/api/update-trip", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                trip_id: currentEditTripId,
                customer_name: document.getElementById("customerName").value,
                vehicle_name: document.getElementById("vehicleName").value,
                pickup_name: document.getElementById("pickupName").value,
                destination_name: document.getElementById("destinationName").value,
                status: document.getElementById("tripStatus").value,
                queue_order: parseInt(document.getElementById("queueOrder").value)
            })
        });
        const data = await res.json();
        if (data.success) {
            showToast("Trip updated successfully", "success");
            closeEditModal();
            await loadTrips();
        } else {
            showToast(data.message || "Failed to update trip", "error");
        }
    } catch (err) {
        console.error(err);
        showToast("Failed to update trip", "error");
    }
}

async function deleteTrip(tripId, vehicleId) {
    if (!confirm("Are you sure you want to delete this trip?")) return;

    try {
        const res = await fetch("/api/clear-trip", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ trip_id: tripId, vehicle_id: vehicleId })
        });
        const data = await res.json();
        if (data.success) {
            showToast("Trip deleted successfully", "success");
            await loadTrips();
        } else {
            showToast(data.message || "Failed to delete trip", "error");
        }
    } catch (err) {
        console.error(err);
        showToast("Failed to delete trip", "error");
    }
}

async function clearAllTrips() {
    if (!confirm("Are you sure you want to delete ALL trips? This cannot be undone.")) return;

    try {
        const res = await fetch("/api/clear-all-trips", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const data = await res.json();
        if (data.success) {
            showToast("All trips cleared successfully", "success");
            await loadTrips();
        } else {
            showToast(data.message || "Failed to clear trips", "error");
        }
    } catch (err) {
        console.error(err);
        showToast("Failed to clear trips", "error");
    }
}

// Initialize
document.getElementById("closeModalBtn").addEventListener("click", closeEditModal);
document.getElementById("cancelEditBtn").addEventListener("click", closeEditModal);
document.getElementById("saveTripBtn").addEventListener("click", saveTrip);
document.getElementById("clearAllBtn").addEventListener("click", clearAllTrips);

loadTrips();
