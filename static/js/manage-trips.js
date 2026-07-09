const MAP_CENTER = [10.8231, 106.6297];
const POLLING_INTERVAL_MS = 15000;
const MIN_ZOOM_FOR_LABELS = 14;

let state = {
    vehicles: [],
    routeData: [],
    manualLocations: {},
    selectedVehicleId: null,
    selectedPickup: null, // Name of saved location or null if custom
    selectedPickupCoords: null, // {lat, lng, name} for custom or saved pickup
    selectedDropoff: null, // Name of saved location or null if custom
    selectedDropoffCoords: null, // {lat, lng, name} for custom or saved dropoff
    tripVehicleSearchTerm: '',
    maxDistanceKm: null,
    activeTripsSearchTerm: '',
    pinMode: null, // 'pickup' or 'dropoff' or null
    editingTripId: null
};

let map = null;
let pickupMarker = null;
let dropoffMarker = null;
let allLocationPolygons = [];
let allLocationLabels = [];
let vehicleMarkers = new Map(); // vehicle.id -> marker


window.addEventListener('DOMContentLoaded', startApp);

function startApp() {
    // Initialize Leaflet map
    map = L.map('map').setView(MAP_CENTER, 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Map click handler for pinning
    map.on('click', handleMapClick);
    
    // Zoom listener to update labels visibility
    map.on('zoomend', updateLabelsVisibility);

    Promise.all([
        fetch('/api/manual-locations'),
        fetch('/api/vehicles'),
        fetch('/api/route-data')
    ]).then(async ([locRes, vehRes, routeRes]) => {
        state.manualLocations = await locRes.json();
        const vehiclesData = await vehRes.json();
        state.vehicles = Array.isArray(vehiclesData) ? vehiclesData : vehiclesData.vehicles;
        state.routeData = await routeRes.json();
        
        populatePickupDropoffSelects();
        renderAllLocations();
        renderAllVehicles();
        updateAllUI();
        setupEventListeners();
        
        setInterval(pollForUpdates, POLLING_INTERVAL_MS);
    }).catch(err => {
        console.error('Error initializing app:', err);
    });
}

function renderAllLocations() {
    // Clear existing
    allLocationPolygons.forEach(p => map.removeLayer(p));
    allLocationLabels.forEach(l => map.removeLayer(l));
    allLocationPolygons = [];
    allLocationLabels = [];

    Object.keys(state.manualLocations).forEach(name => {
        const loc = state.manualLocations[name];
        let polygonsToAdd = [];
        if (loc.polygons && Array.isArray(loc.polygons)) {
            polygonsToAdd = loc.polygons;
        } else if (loc.corners) {
            polygonsToAdd = [loc.corners];
        }

        polygonsToAdd.forEach(polygon => {
            const poly = L.polygon(polygon, {
                color: "#2563eb",
                weight: 3,
                opacity: 0.7,
                fillOpacity: 0.15
            }).addTo(map);
            allLocationPolygons.push(poly);
        });

        // Add label at centroid
        const centroid = getLocationCentroid(loc);
        if (centroid) {
            const label = L.marker([centroid.lat, centroid.lng], {
                icon: L.divIcon({
                    className: 'location-name-label',
                    html: `<div style="
                        background: white;
                        padding: 6px 12px;
                        border-radius: 4px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                        font-weight: 600;
                        font-size: 14px;
                        color: #111827;
                        white-space: nowrap;
                    ">${escapeHtml(name)}</div>`,
                    iconSize: [null, null],
                    iconAnchor: [0, 0]
                })
            });
            if (map.getZoom() >= MIN_ZOOM_FOR_LABELS) {
                label.addTo(map);
            }
            allLocationLabels.push(label);
        }
    });
    updateLabelsVisibility();
}

function updateLabelsVisibility() {
    const currentZoom = map.getZoom();
    allLocationLabels.forEach(label => {
        if (currentZoom >= MIN_ZOOM_FOR_LABELS) {
            if (!map.hasLayer(label)) {
                label.addTo(map);
            }
        } else {
            if (map.hasLayer(label)) {
                map.removeLayer(label);
            }
        }
    });
}

function renderAllVehicles() {
    // Clear old markers
    vehicleMarkers.forEach((marker, id) => map.removeLayer(marker));
    vehicleMarkers.clear();

    state.vehicles.forEach(vehicle => {
        const isSelected = vehicle.id === state.selectedVehicleId;
        const marker = L.marker([vehicle.latitude, vehicle.longitude], {
            icon: createIcon(vehicle, isSelected)
        }).addTo(map);
        marker.bindPopup(`<strong>${escapeHtml(vehicle.device_name || vehicle.id)}</strong><br>Status: ${escapeHtml(vehicle.vehicle_status || 'Unknown')}`);
        vehicleMarkers.set(vehicle.id, marker);
    });
}

function createIcon(vehicle, isSelected) {
    const color = isSelected ? '#2563eb' : '#10b981';
    const borderColor = isSelected ? '#1d4ed8' : '#059669';
    return L.divIcon({
        className: 'vehicle-marker',
        html: `<div style="
            width: 32px;
            height: 32px;
            background: ${color};
            border: 3px solid ${borderColor};
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        ">🚗</div>`,
        iconSize: [32, 32],
        iconAnchor: [16, 16]
    });
}

function updateVehicleMarker(vehicle) {
    const existingMarker = vehicleMarkers.get(vehicle.id);
    if (existingMarker) {
        existingMarker.setLatLng([vehicle.latitude, vehicle.longitude]);
        const isSelected = vehicle.id === state.selectedVehicleId;
        existingMarker.setIcon(createIcon(vehicle, isSelected));
    } else {
        const isSelected = vehicle.id === state.selectedVehicleId;
        const marker = L.marker([vehicle.latitude, vehicle.longitude], {
            icon: createIcon(vehicle, isSelected)
        }).addTo(map);
        marker.bindPopup(`<strong>${escapeHtml(vehicle.device_name || vehicle.id)}</strong><br>Status: ${escapeHtml(vehicle.vehicle_status || 'Unknown')}`);
        vehicleMarkers.set(vehicle.id, marker);
    }
}


function setupEventListeners() {
    const pickupSelect = document.getElementById('pickup-select');
    const dropoffSelect = document.getElementById('dropoff-select');
    
    pickupSelect.addEventListener('change', handlePickupChange);
    dropoffSelect.addEventListener('change', handleDropoffChange);
    
    document.getElementById('create-trip-btn').addEventListener('click', handleCreateTrip);
    
    const tripVehicleSearch = document.getElementById('trip-vehicle-search');
    tripVehicleSearch.addEventListener('input', (e) => {
        state.tripVehicleSearchTerm = e.target.value.toLowerCase();
        updateVehicleSuggestions();
    });
    
    const maxDistanceFilter = document.getElementById('max-distance-filter');
    maxDistanceFilter.addEventListener('input', (e) => {
        const value = e.target.value;
        state.maxDistanceKm = value ? parseFloat(value) : null;
        updateVehicleSuggestions();
    });
    
    const activeTripsSearch = document.getElementById('active-trips-search');
    activeTripsSearch.addEventListener('input', (e) => {
        state.activeTripsSearchTerm = e.target.value.toLowerCase();
        updateTripsTable();
    });

    // Geocoding search inputs
    const pickupSearch = document.getElementById('pickup-search');
    const dropoffSearch = document.getElementById('dropoff-search');
    
    let pickupDebounce = null;
    let dropoffDebounce = null;

    pickupSearch.addEventListener('input', (e) => {
        clearTimeout(pickupDebounce);
        pickupDebounce = setTimeout(() => searchGeocode(e.target.value, 'pickup'), 300);
    });
    
    dropoffSearch.addEventListener('input', (e) => {
        clearTimeout(dropoffDebounce);
        dropoffDebounce = setTimeout(() => searchGeocode(e.target.value, 'dropoff'), 300);
    });

    // Pin buttons
    document.getElementById('pickup-pin-btn').addEventListener('click', () => {
        state.pinMode = state.pinMode === 'pickup' ? null : 'pickup';
        updatePinModeUI();
    });
    document.getElementById('dropoff-pin-btn').addEventListener('click', () => {
        state.pinMode = state.pinMode === 'dropoff' ? null : 'dropoff';
        updatePinModeUI();
    });

    // Customer name input
    const customerNameInput = document.getElementById('customer-name');
    customerNameInput.addEventListener('input', updateCreateButtonState);

    // Cancel edit button
    document.getElementById('cancel-edit-btn').addEventListener('click', cancelEditingTrip);
}

function updatePinModeUI() {
    const pickupBtn = document.getElementById('pickup-pin-btn');
    const dropoffBtn = document.getElementById('dropoff-pin-btn');
    
    pickupBtn.style.background = state.pinMode === 'pickup' ? '#2563eb' : 'rgba(0,0,0,0.15)';
    dropoffBtn.style.color = 'white';
    dropoffBtn.style.background = state.pinMode === 'dropoff' ? '#2563eb' : 'rgba(0,0,0,0.15)';
}

async function searchGeocode(query, type) {
    const suggestionsContainer = document.getElementById(`${type}-suggestions`);
    if (!query || query.trim().length < 3) {
        suggestionsContainer.style.display = 'none';
        return;
    }

    try {
        const res = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        if (data.success && data.results.length > 0) {
            suggestionsContainer.innerHTML = data.results.map(result => `
                <div class="geocode-suggestion-item"
                     data-lat="${result.lat}" 
                     data-lng="${result.lng}" 
                     data-name="${escapeHtml(result.name)}">
                    ${escapeHtml(result.name)}
                </div>
            `).join('');
            suggestionsContainer.style.display = 'block';

            suggestionsContainer.querySelectorAll('[data-lat]').forEach(el => {
                el.addEventListener('click', () => {
                    const lat = parseFloat(el.dataset.lat);
                    const lng = parseFloat(el.dataset.lng);
                    const name = el.dataset.name;
                    selectCustomLocation(type, lat, lng, name);
                    suggestionsContainer.style.display = 'none';
                    document.getElementById(`${type}-search`).value = name;
                });
            });
        } else {
            suggestionsContainer.innerHTML = '<div class="geocode-suggestion-item geocode-no-results">No results found</div>';
            suggestionsContainer.style.display = 'block';
        }
    } catch (err) {
        console.error('Geocoding error:', err);
    }
}

function selectCustomLocation(type, lat, lng, name) {
    const coords = { lat, lng, name: name || `Custom ${type}` };
    if (type === 'pickup') {
        state.selectedPickup = null;
        state.selectedPickupCoords = coords;
        document.getElementById('pickup-select').value = '';
        if (pickupMarker) map.removeLayer(pickupMarker);
        pickupMarker = L.marker([lat, lng], {
            icon: L.divIcon({
                className: 'pickup-marker',
                html: `<div style="
                    width: 36px;
                    height: 36px;
                    background: #8b5cf6;
                    border: 3px solid #6d28d9;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 16px;
                    box-shadow: 0 2px 8px rgba(139,92,246,0.5);
                ">P</div>`,
                iconSize: [36, 36],
                iconAnchor: [18, 18]
            })
        }).addTo(map);
    } else {
        state.selectedDropoff = null;
        state.selectedDropoffCoords = coords;
        document.getElementById('dropoff-select').value = '';
        if (dropoffMarker) map.removeLayer(dropoffMarker);
        dropoffMarker = L.marker([lat, lng], {
            icon: L.divIcon({
                className: 'dropoff-marker',
                html: `<div style="
                    width: 36px;
                    height: 36px;
                    background: #f97316;
                    border: 3px solid #c2410c;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 16px;
                    box-shadow: 0 2px 8px rgba(249,115,22,0.5);
                ">D</div>`,
                iconSize: [36, 36],
                iconAnchor: [18, 18]
            })
        }).addTo(map);
    }
    
    // Fit map bounds to include pickup, dropoff, and selected vehicle (if any)
    const bounds = L.latLngBounds();
    if (state.selectedPickupCoords) {
        bounds.extend([state.selectedPickupCoords.lat, state.selectedPickupCoords.lng]);
    }
    if (state.selectedDropoffCoords) {
        bounds.extend([state.selectedDropoffCoords.lat, state.selectedDropoffCoords.lng]);
    }
    if (state.selectedVehicleId) {
        const vehicle = state.vehicles.find(v => v.id === state.selectedVehicleId);
        if (vehicle) {
            bounds.extend([vehicle.latitude, vehicle.longitude]);
        }
    }
    if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [30, 30] });
    }
    
    updateVehicleSuggestions();
    updateCreateButtonState();
}

function handleMapClick(e) {
    if (state.pinMode) {
        selectCustomLocation(state.pinMode, e.latlng.lat, e.latlng.lng, 'Pinned Location');
        document.getElementById(`${state.pinMode}-search`).value = 'Custom Pinned Location';
        state.pinMode = null;
        updatePinModeUI();
    }
}


function populatePickupDropoffSelects() {
    const pickupSelect = document.getElementById('pickup-select');
    const dropoffSelect = document.getElementById('dropoff-select');
    
    pickupSelect.innerHTML = '<option value="">-- Select Saved Location --</option>';
    dropoffSelect.innerHTML = '<option value="">-- Select Saved Location --</option>';
    
    Object.keys(state.manualLocations).forEach(name => {
        const optionPickup = document.createElement('option');
        optionPickup.value = name;
        optionPickup.textContent = name;
        pickupSelect.appendChild(optionPickup);
        
        const optionDropoff = document.createElement('option');
        optionDropoff.value = name;
        optionDropoff.textContent = name;
        dropoffSelect.appendChild(optionDropoff);
    });
}

function getLocationCoords(locationName, customCoords) {
    if (customCoords) {
        return customCoords;
    }
    if (!locationName) return null;
    const loc = state.manualLocations[locationName];
    if (!loc) return null;
    const centroid = getLocationCentroid(loc);
    return centroid ? { ...centroid, name: locationName } : null;
}

function calculateDistance(lat1, lng1, lat2, lng2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLng/2) * Math.sin(dLng/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

function handlePickupChange(e) {
    const name = e.target.value;
    if (name) {
        state.selectedPickup = name;
        const coords = getLocationCoords(name);
        state.selectedPickupCoords = coords;
        document.getElementById('pickup-search').value = '';
        if (pickupMarker) map.removeLayer(pickupMarker);
        pickupMarker = L.marker([coords.lat, coords.lng], {
            icon: L.divIcon({
                className: 'pickup-marker',
                html: `<div style="
                    width: 36px;
                    height: 36px;
                    background: #8b5cf6;
                    border: 3px solid #6d28d9;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 16px;
                    box-shadow: 0 2px 8px rgba(139,92,246,0.5);
                ">P</div>`,
                iconSize: [36, 36],
                iconAnchor: [18, 18]
            })
        }).addTo(map);
    } else {
        state.selectedPickup = null;
        state.selectedPickupCoords = null;
        if (pickupMarker) map.removeLayer(pickupMarker);
    }
    
    // Fit map bounds to include pickup, dropoff, and selected vehicle (if any)
    const bounds = L.latLngBounds();
    if (state.selectedPickupCoords) {
        bounds.extend([state.selectedPickupCoords.lat, state.selectedPickupCoords.lng]);
    }
    if (state.selectedDropoffCoords) {
        bounds.extend([state.selectedDropoffCoords.lat, state.selectedDropoffCoords.lng]);
    }
    if (state.selectedVehicleId) {
        const vehicle = state.vehicles.find(v => v.id === state.selectedVehicleId);
        if (vehicle) {
            bounds.extend([vehicle.latitude, vehicle.longitude]);
        }
    }
    if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [30, 30] });
    }
    
    updateVehicleSuggestions();
    updateCreateButtonState();
}

function handleDropoffChange(e) {
    const name = e.target.value;
    if (name) {
        state.selectedDropoff = name;
        const coords = getLocationCoords(name);
        state.selectedDropoffCoords = coords;
        document.getElementById('dropoff-search').value = '';
        if (dropoffMarker) map.removeLayer(dropoffMarker);
        dropoffMarker = L.marker([coords.lat, coords.lng], {
            icon: L.divIcon({
                className: 'dropoff-marker',
                html: `<div style="
                    width: 36px;
                    height: 36px;
                    background: #f97316;
                    border: 3px solid #c2410c;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 16px;
                    box-shadow: 0 2px 8px rgba(249,115,22,0.5);
                ">D</div>`,
                iconSize: [36, 36],
                iconAnchor: [18, 18]
            })
        }).addTo(map);
    } else {
        state.selectedDropoff = null;
        state.selectedDropoffCoords = null;
        if (dropoffMarker) map.removeLayer(dropoffMarker);
    }
    
    // Fit map bounds to include pickup, dropoff, and selected vehicle (if any)
    const bounds = L.latLngBounds();
    if (state.selectedPickupCoords) {
        bounds.extend([state.selectedPickupCoords.lat, state.selectedPickupCoords.lng]);
    }
    if (state.selectedDropoffCoords) {
        bounds.extend([state.selectedDropoffCoords.lat, state.selectedDropoffCoords.lng]);
    }
    if (state.selectedVehicleId) {
        const vehicle = state.vehicles.find(v => v.id === state.selectedVehicleId);
        if (vehicle) {
            bounds.extend([vehicle.latitude, vehicle.longitude]);
        }
    }
    if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [30, 30] });
    }
    
    updateCreateButtonState();
}


function updateVehicleSuggestions() {
    const suggestionsContainer = document.getElementById('vehicle-suggestions');
    
    if (!state.selectedPickupCoords) {
        suggestionsContainer.innerHTML = '<p style="color:#6c757d;">Select a pickup location to see suggestions</p>';
        return;
    }
    
    let sortedVehicles = [...state.vehicles].sort((a, b) => {
        const distA = calculateDistance(a.latitude, a.longitude, state.selectedPickupCoords.lat, state.selectedPickupCoords.lng);
        const distB = calculateDistance(b.latitude, b.longitude, state.selectedPickupCoords.lat, state.selectedPickupCoords.lng);
        return distA - distB;
    });
    
    if (state.tripVehicleSearchTerm) {
        sortedVehicles = sortedVehicles.filter(vehicle => {
            const plate = (vehicle.device_name || '').toLowerCase();
            const id = (vehicle.id || '').toLowerCase();
            return plate.includes(state.tripVehicleSearchTerm) || id.includes(state.tripVehicleSearchTerm);
        });
    }
    
    if (state.maxDistanceKm !== null && !isNaN(state.maxDistanceKm)) {
        sortedVehicles = sortedVehicles.filter(vehicle => {
            const distance = calculateDistance(vehicle.latitude, vehicle.longitude, state.selectedPickupCoords.lat, state.selectedPickupCoords.lng);
            return distance <= state.maxDistanceKm;
        });
    }
    
    if (sortedVehicles.length === 0) {
        suggestionsContainer.innerHTML = '<p style="color:#6c757d;">No vehicles match your search</p>';
        return;
    }
    
    suggestionsContainer.innerHTML = '';
    sortedVehicles.forEach(vehicle => {
        const distance = calculateDistance(vehicle.latitude, vehicle.longitude, state.selectedPickupCoords.lat, state.selectedPickupCoords.lng);
        const statusText = vehicle.vehicle_status || 'Unknown';
        const isSelected = vehicle.id === state.selectedVehicleId;
        
        const suggestionEl = document.createElement('div');
        suggestionEl.className = `suggestion-item ${isSelected ? 'active' : ''}`;
        suggestionEl.innerHTML = `
            <div class="suggestion-info">
                <div class="suggestion-name">${escapeHtml(vehicle.device_name || vehicle.id)}</div>
                <div class="suggestion-details">
                    ${escapeHtml(vehicle.car_type || vehicle.vehicle_type || 'Unknown type')} • 
                    Status: ${escapeHtml(statusText)} • 
                    Distance to pickup: ${distance.toFixed(2)} km
                </div>
            </div>
        `;
        
        suggestionEl.addEventListener('click', () => {
            state.selectedVehicleId = vehicle.id;
            // Update all vehicle markers (to highlight selected)
            state.vehicles.forEach(updateVehicleMarker);
            // Fit map to selected vehicle and pickup/dropoff
            const bounds = L.latLngBounds([[vehicle.latitude, vehicle.longitude]]);
            if (state.selectedPickupCoords) {
                bounds.extend([state.selectedPickupCoords.lat, state.selectedPickupCoords.lng]);
            }
            if (state.selectedDropoffCoords) {
                bounds.extend([state.selectedDropoffCoords.lat, state.selectedDropoffCoords.lng]);
            }
            map.fitBounds(bounds, { padding: [30, 30] });
            
            updateVehicleSuggestions();
            updateCreateButtonState();
        });
        
        suggestionsContainer.appendChild(suggestionEl);
    });
}


function updateCreateButtonState() {
    const btn = document.getElementById('create-trip-btn');
    const customerName = document.getElementById('customer-name').value.trim();
    btn.disabled = !(state.selectedPickupCoords && state.selectedDropoffCoords && state.selectedVehicleId && customerName);
}

async function handleCreateTrip() {
    const pickupCoords = state.selectedPickupCoords;
    const dropoffCoords = state.selectedDropoffCoords;
    if (!pickupCoords) {
        showToast('Invalid pickup location', 'error');
        return;
    }
    if (!dropoffCoords) {
        showToast('Invalid dropoff location', 'error');
        return;
    }
    
    const customerName = document.getElementById('customer-name').value.trim();
    
    const vehicle = state.vehicles.find(v => v.id === state.selectedVehicleId);
    if (!vehicle) {
        showToast('Vehicle not found', 'error');
        return;
    }
    
    const btn = document.getElementById('create-trip-btn');
    btn.disabled = true;
    btn.textContent = state.editingTripId ? 'Updating...' : 'Assigning...';
    
    try {
        let setDestRes;
        if (state.editingTripId) {
            setDestRes = await fetch('/api/update-trip', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    trip_id: state.editingTripId,
                    vehicle_id: vehicle.id,
                    vehicle_name: vehicle.device_name || vehicle.id,
                    destination_lat: dropoffCoords.lat,
                    destination_lng: dropoffCoords.lng,
                    destination_name: dropoffCoords.name,
                    pickup_lat: pickupCoords.lat,
                    pickup_lng: pickupCoords.lng,
                    pickup_name: pickupCoords.name,
                    customer_name: customerName,
                    vehicle_type: vehicle.car_type || vehicle.vehicle_type,
                    phase: parseInt(document.getElementById('trip-phase').value, 10)
                })
            });
        } else {
            setDestRes = await fetch('/api/set-destination', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    vehicle_id: vehicle.id,
                    vehicle_name: vehicle.device_name || vehicle.id,
                    destination_lat: dropoffCoords.lat,
                    destination_lng: dropoffCoords.lng,
                    destination_name: dropoffCoords.name,
                    pickup_lat: pickupCoords.lat,
                    pickup_lng: pickupCoords.lng,
                    pickup_name: pickupCoords.name,
                    customer_name: customerName,
                    vehicle_type: vehicle.car_type || vehicle.vehicle_type
                })
            });
        }
        
        const setDestData = await setDestRes.json();
        if (!setDestData.success) {
            throw new Error(setDestData.message || 'Failed to assign trip');
        }
        
        const refreshRes = await fetch('/api/refresh-routes', { method: 'POST' });
        const refreshData = await refreshRes.json();
        
        if (refreshData.success) {
            state.routeData = refreshData.route_data;
            updateTripsTable();
            showToast(state.editingTripId ? 'Trip updated successfully!' : 'Trip assigned successfully!', 'success');
        } else {
            throw new Error('Failed to refresh routes');
        }
        
        state.editingTripId = null;
        document.getElementById('form-card-title').textContent = 'Create New Trip';
        document.getElementById('cancel-edit-btn').style.display = 'none';
        
        state.selectedPickup = null;
        state.selectedPickupCoords = null;
        state.selectedDropoff = null;
        state.selectedDropoffCoords = null;
        state.selectedVehicleId = null;
        document.getElementById('pickup-select').value = '';
        document.getElementById('pickup-search').value = '';
        document.getElementById('dropoff-select').value = '';
        document.getElementById('dropoff-search').value = '';
        document.getElementById('customer-name').value = '';
        if (pickupMarker) map.removeLayer(pickupMarker);
        if (dropoffMarker) map.removeLayer(dropoffMarker);
        updateVehicleSuggestions();
        updateCreateButtonState();
        
        state.vehicles.forEach(updateVehicleMarker);
        
    } catch (err) {
        console.error('Error saving trip:', err);
        showToast('Error saving trip: ' + (err.message || 'Unknown error'), 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = state.editingTripId ? 'Update Assigned Trip' : 'Assign Trip to Selected Vehicle';
    }
}

function pollForUpdates() {
    Promise.all([
        fetch('/api/vehicles'),
        fetch('/api/route-data')
    ]).then(async ([vehRes, routeRes]) => {
        const vehiclesData = await vehRes.json();
        state.vehicles = Array.isArray(vehiclesData) ? vehiclesData : vehiclesData.vehicles;
        state.routeData = await routeRes.json();
        
        renderAllVehicles();
        updateAllUI();
    }).catch(err => {
        console.error('Error polling for updates:', err);
    });
}


function updateAllUI() {
    updateTripsTable();
    updateVehicleSuggestions();
}

function updateTripsTable() {
    const tbody = document.getElementById('trips-table-body');
    tbody.innerHTML = '';
    
    if (!state.routeData || state.routeData.length === 0) {
        const tr = document.createElement('tr');
        tr.innerHTML = '<td colspan="10" style="text-align: center; padding: 30px; color:#6c757d;">No active trips</td>';
        tbody.appendChild(tr);
        return;
    }
    
    let filteredTrips = state.routeData;
    
    if (state.activeTripsSearchTerm) {
        filteredTrips = filteredTrips.filter(trip => {
            const plate = (trip.vehicle_name || '').toLowerCase();
            const id = (trip.vehicle_id || '').toLowerCase();
            const customer = (trip.customer_name || '').toLowerCase();
            return plate.includes(state.activeTripsSearchTerm) || id.includes(state.activeTripsSearchTerm) || customer.includes(state.activeTripsSearchTerm);
        });
    }
    
    if (filteredTrips.length === 0) {
        const tr = document.createElement('tr');
        tr.innerHTML = '<td colspan="10" style="text-align: center; padding: 30px; color:#6c757d;">No matching trips</td>';
        tbody.appendChild(tr);
        return;
    }
    
    const groupedTrips = {};
    filteredTrips.forEach(trip => {
        const plate = trip.vehicle_name || trip.vehicle_id || 'Unknown';
        if (!groupedTrips[plate]) {
            groupedTrips[plate] = [];
        }
        groupedTrips[plate].push(trip);
    });
    
    Object.keys(groupedTrips).sort().forEach(plate => {
        const trips = groupedTrips[plate].sort((a, b) => a.queue_order - b.queue_order);
        
        const headerTr = document.createElement('tr');
        headerTr.style.backgroundColor = '#f8f9fa';
        headerTr.innerHTML = `
            <td colspan="10" style="font-weight: 600; padding: 12px 15px; color: #495057;">
                ${escapeHtml(plate)}
            </td>
        `;
        tbody.appendChild(headerTr);
        
        trips.forEach(trip => {
            const etaText = trip.status === 'active' ? formatEta(trip.eta_seconds) : 'N/A';
            const distanceText = trip.status === 'active' ? trip.distance_remaining_km.toFixed(2) : 'N/A';
            const statusColor = trip.status === 'active' ? '#10b981' : (trip.status === 'queued' ? '#f59e0b' : '#6b7280');
            
            // Calculate phase text
            let phaseText = 'N/A';
            if (trip.status === 'active') {
                const phaseNum = Number(trip.phase) || 1;
                if (phaseNum === 1) {
                    if (trip.pickup_name) {
                        phaseText = `Phase 1: To ${trip.pickup_name}`;
                    } else {
                        phaseText = `Phase 1: To ${trip.destination_name || 'Destination'}`;
                    }
                } else if (phaseNum === 2) {
                    phaseText = `Phase 2: To ${trip.destination_name || 'Destination'}`;
                } else {
                    phaseText = `Phase ${phaseNum}: To ${trip.destination_name || 'Destination'}`;
                }
            }
            
            const actionsTd = document.createElement('td');
            actionsTd.style.display = 'flex';
            actionsTd.style.gap = '6px';
            
            const editBtn = document.createElement('button');
            editBtn.className = 'btn-secondary';
            editBtn.textContent = 'Edit';
            editBtn.style.padding = '6px 12px';
            editBtn.style.fontSize = '13px';
            editBtn.style.height = '30px';
            editBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                startEditingTrip(trip);
            });
            
            const cancelBtn = document.createElement('button');
            cancelBtn.className = 'btn-danger';
            cancelBtn.textContent = 'Cancel';
            cancelBtn.style.padding = '6px 12px';
            cancelBtn.style.fontSize = '13px';
            cancelBtn.style.height = '30px';
            cancelBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                cancelTrip(trip.trip_id);
            });
            
            const clearBtn = document.createElement('button');
            clearBtn.textContent = 'Delete';
            clearBtn.style.padding = '6px 12px';
            clearBtn.style.fontSize = '13px';
            clearBtn.style.height = '30px';
            clearBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                clearTrip(trip.trip_id, trip.vehicle_id);
            });
            
            actionsTd.appendChild(editBtn);
            if (trip.status !== 'canceled') {
                actionsTd.appendChild(cancelBtn);
            }
            actionsTd.appendChild(clearBtn);
            
            // Compute duration
            let durationText = '';
            if (trip.status === 'active' && trip.created_at) {
                const created = new Date(trip.created_at + 'Z');
                const elapsed = Math.floor((Date.now() - created.getTime()) / 1000);
                if (elapsed > 0) {
                    const mins = Math.floor(elapsed / 60);
                    const hrs = Math.floor(mins / 60);
                    durationText = hrs > 0 ? `${hrs}h ${mins % 60}m` : `${mins}m`;
                }
            } else if (trip.status === 'completed') {
                durationText = 'Done';
            }
            
            const driverName = trip.driver_name || 'N/A';
            
            const tr = document.createElement('tr');
            tr.style.cursor = 'pointer';
            tr.innerHTML = `
                <td>${escapeHtml(trip.vehicle_name)}</td>
                <td>${escapeHtml(driverName)}</td>
                <td>${escapeHtml(trip.customer_name || 'N/A')}</td>
                <td>${escapeHtml(trip.pickup_name || 'N/A')}</td>
                <td>${escapeHtml(trip.destination_name || 'N/A')}</td>
                <td>${escapeHtml(phaseText)}</td>
                <td>${distanceText}</td>
                <td>${etaText}</td>
                <td>${escapeHtml(durationText)}</td>
                <td><span style="display:inline-block; padding:4px 10px; border-radius:20px; background:${statusColor}; color:white; font-size:12px; font-weight:600;">${escapeHtml(trip.status)}</span></td>
            `;
            tr.appendChild(actionsTd);
            
            tr.addEventListener('click', (e) => {
                if (e.target.tagName === 'BUTTON') return;
                window.location.href = `/?focusVehicle=${encodeURIComponent(trip.vehicle_id)}`;
            });
            
            tbody.appendChild(tr);
        });
    });
}

async function cancelTrip(tripId) {
    const reason = prompt('Cancel reason (optional):', 'Manual cancellation');
    if (reason === null) return;
    try {
        const res = await fetch('/api/cancel-trip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ trip_id: tripId, reason: reason || 'Manual cancellation' })
        });
        const data = await res.json();
        if (data.success) {
            showToast('Trip canceled', 'success');
            pollForUpdates();
        } else {
            showToast(data.message || 'Failed to cancel trip', 'error');
        }
    } catch (err) {
        showToast('Error canceling trip', 'error');
    }
}

async function clearTrip(tripId, vehicleId) {
    if (!confirm('Are you sure you want to remove this trip?')) return;
    
    try {
        const conn = await fetch('/api/clear-trip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                trip_id: tripId,
                vehicle_id: vehicleId
            })
        });
        
        const data = await conn.json();
        if (data.success) {
            const refreshRes = await fetch('/api/refresh-routes', { method: 'POST' });
            const refreshData = await refreshRes.json();
            if (refreshData.success) {
                state.routeData = refreshData.route_data;
                updateTripsTable();
                showToast('Trip removed!', 'success');
            }
        } else {
            showToast('Error removing trip: ' + data.message, 'error');
        }
    } catch (err) {
        console.error(err);
        showToast('Error removing trip', 'error');
    }
}

function formatEta(seconds) {
    if (seconds === null || seconds === undefined || isNaN(seconds)) {
        return 'Calculating...';
    }
    const etaDate = new Date(Date.now() + (seconds * 1000));
    const hours = String(etaDate.getHours()).padStart(2, '0');
    const minutes = String(etaDate.getMinutes()).padStart(2, '0');
    return `${hours}:${minutes}`;
}

function escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    })[char]);
}

function cancelEditingTrip() {
    state.editingTripId = null;
    document.getElementById('form-card-title').textContent = 'Create New Trip';
    document.getElementById('cancel-edit-btn').style.display = 'none';
    document.getElementById('phase-form-group').style.display = 'none';
    
    // Clear fields
    state.selectedPickup = null;
    state.selectedPickupCoords = null;
    state.selectedDropoff = null;
    state.selectedDropoffCoords = null;
    state.selectedVehicleId = null;
    document.getElementById('pickup-select').value = '';
    document.getElementById('pickup-search').value = '';
    document.getElementById('dropoff-select').value = '';
    document.getElementById('dropoff-search').value = '';
    document.getElementById('customer-name').value = '';
    document.getElementById('trip-phase').value = '1';
    if (pickupMarker) map.removeLayer(pickupMarker);
    if (dropoffMarker) map.removeLayer(dropoffMarker);
    
    // Refresh vehicle lists & buttons
    updateVehicleSuggestions();
    updateCreateButtonState();
    
    // Re-render vehicles to clear highlight
    state.vehicles.forEach(updateVehicleMarker);
    
    // Reset create button text
    document.getElementById('create-trip-btn').textContent = 'Assign Trip to Selected Vehicle';
}

function startEditingTrip(trip) {
    // Enable edit mode
    state.editingTripId = trip.trip_id;
    document.getElementById('form-card-title').textContent = `Edit Trip (Vehicle: ${trip.vehicle_name})`;
    document.getElementById('cancel-edit-btn').style.display = 'inline-block';
    document.getElementById('phase-form-group').style.display = 'block';
    const createBtn = document.getElementById('create-trip-btn');
    createBtn.textContent = 'Update Assigned Trip';
    
    // Populate customer name
    document.getElementById('customer-name').value = trip.customer_name || '';
    
    // Populate phase
    document.getElementById('trip-phase').value = trip.phase || '1';
    
    // Populate pickup
    const pickupSelect = document.getElementById('pickup-select');
    let hasPickupInSelect = false;
    for (let option of pickupSelect.options) {
        if (option.value === trip.pickup_name) {
            hasPickupInSelect = true;
            break;
        }
    }
    if (hasPickupInSelect && trip.pickup_name) {
        pickupSelect.value = trip.pickup_name;
        state.selectedPickup = trip.pickup_name;
        state.selectedPickupCoords = getLocationCoords(trip.pickup_name);
        document.getElementById('pickup-search').value = '';
    } else {
        pickupSelect.value = '';
        state.selectedPickup = null;
        state.selectedPickupCoords = { lat: trip.pickup_lat, lng: trip.pickup_lng, name: trip.pickup_name || 'Custom Pickup' };
        document.getElementById('pickup-search').value = trip.pickup_name || '';
    }
    
    // Re-create pickup marker
    if (pickupMarker) map.removeLayer(pickupMarker);
    if (state.selectedPickupCoords) {
        pickupMarker = L.marker([state.selectedPickupCoords.lat, state.selectedPickupCoords.lng], {
            icon: L.divIcon({
                className: 'pickup-marker',
                html: `<div style="
                    width: 36px;
                    height: 36px;
                    background: #8b5cf6;
                    border: 3px solid #6d28d9;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 16px;
                    box-shadow: 0 2px 8px rgba(139,92,246,0.5);
                ">P</div>`,
                iconSize: [36, 36],
                iconAnchor: [18, 18]
            })
        }).addTo(map);
    }
    
    // Populate dropoff
    const dropoffSelect = document.getElementById('dropoff-select');
    let hasDropoffInSelect = false;
    for (let option of dropoffSelect.options) {
        if (option.value === trip.destination_name) {
            hasDropoffInSelect = true;
            break;
        }
    }
    if (hasDropoffInSelect && trip.destination_name) {
        dropoffSelect.value = trip.destination_name;
        state.selectedDropoff = trip.destination_name;
        state.selectedDropoffCoords = getLocationCoords(trip.destination_name);
        document.getElementById('dropoff-search').value = '';
    } else {
        dropoffSelect.value = '';
        state.selectedDropoff = null;
        state.selectedDropoffCoords = { lat: trip.destination_lat, lng: trip.destination_lng, name: trip.destination_name || 'Custom Dropoff' };
        document.getElementById('dropoff-search').value = trip.destination_name || '';
    }
    
    // Re-create dropoff marker
    if (dropoffMarker) map.removeLayer(dropoffMarker);
    if (state.selectedDropoffCoords) {
        dropoffMarker = L.marker([state.selectedDropoffCoords.lat, state.selectedDropoffCoords.lng], {
            icon: L.divIcon({
                className: 'dropoff-marker',
                html: `<div style="
                    width: 36px;
                    height: 36px;
                    background: #f97316;
                    border: 3px solid #c2410c;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 16px;
                    box-shadow: 0 2px 8px rgba(249,115,22,0.5);
                ">D</div>`,
                iconSize: [36, 36],
                iconAnchor: [18, 18]
            })
        }).addTo(map);
    }
    
    // Populate vehicle
    state.selectedVehicleId = trip.vehicle_id;
    state.vehicles.forEach(updateVehicleMarker);
    
    // Fit map bounds to show trip details
    const bounds = L.latLngBounds();
    if (state.selectedPickupCoords) bounds.extend([state.selectedPickupCoords.lat, state.selectedPickupCoords.lng]);
    if (state.selectedDropoffCoords) bounds.extend([state.selectedDropoffCoords.lat, state.selectedDropoffCoords.lng]);
    const vehicle = state.vehicles.find(v => v.id === state.selectedVehicleId);
    if (vehicle) bounds.extend([vehicle.latitude, vehicle.longitude]);
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [30, 30] });
    
    // Update vehicle suggestions & button state
    updateVehicleSuggestions();
    updateCreateButtonState();
    
    // Scroll to form card
    document.getElementById('form-card-title').scrollIntoView({ behavior: 'smooth' });
}

