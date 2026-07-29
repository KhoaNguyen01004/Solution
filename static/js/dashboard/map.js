// ================================================================
// Dispatch Dashboard — Map Module (Center Panel)
// ================================================================
window.DASH = window.DASH || {};

(function () {
  'use strict';

  let mapInstance = null;
  let vehicleMarkerLayer = null;
  let stopMarkerLayer = null;
  let routeLayer = null;
  let vehicleMarkers = {}; // assignment_id → marker
  let currentZoomAssignment = null;

  function escapeHtml(str) {
    if (str == null) return '';
    const d = document.createElement('div');
    d.appendChild(document.createTextNode(String(str)));
    return d.innerHTML;
  }

  function statusColor(status) {
    const map = {
      completed: '#2ea043',
      current: '#fb923c',
      arrived: '#fb923c',
      enroute: '#22d3ee',
      planned: '#9ca3af',
      skipped: '#eab308',
      cancelled: '#ef4444',
    };
    return map[status] || '#9ca3af';
  }

  DASH.map = {
    init() {
      if (mapInstance) return;

      mapInstance = L.map('dashboardMap', {
        zoomControl: true,
        center: [10.8231, 106.6297],
        zoom: 11,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors',
      }).addTo(mapInstance);

      vehicleMarkerLayer = L.layerGroup().addTo(mapInstance);
      stopMarkerLayer = L.layerGroup().addTo(mapInstance);
      routeLayer = L.layerGroup().addTo(mapInstance);
    },

    updateVehicles(assignments) {
      if (!mapInstance) return;
      vehicleMarkerLayer.clearLayers();
      vehicleMarkers = {};

      assignments.forEach((a) => {
        const gps = a.gps;
        if (!gps || !gps.latitude || !gps.longitude) return;

        const lat = parseFloat(gps.latitude);
        const lng = parseFloat(gps.longitude);
        if (isNaN(lat) || isNaN(lng)) return;

        const isSelected = a.assignment_id === DASH.state.selectedAssignmentId;
        const label = a.plate_number || 'V' + a.assignment_id;
        const status = a.plan_status || 'confirmed';
        const borderColor = isSelected ? '#fb923c' : statusColor(status);

        const icon = L.divIcon({
          className: '',
          html: `<div class="vehicle-marker-label" style="border-color:${borderColor};">${escapeHtml(label)}</div>`,
          iconSize: [0, 0],
          iconAnchor: [0, 0],
        });

        const marker = L.marker([lat, lng], { icon }).addTo(vehicleMarkerLayer);
        const stopName = a.current_stop ? (a.current_stop.station_name || a.current_stop.station_code || 'Stop #' + a.current_stop.planned_sequence) : 'No active stop';
        const progress = a.progress || {};
        const popupHtml = `
          <div style="font-size:12px;min-width:160px;">
            <strong>${escapeHtml(label)}</strong><br/>
            Driver: ${escapeHtml(a.current_driver || 'N/A')}<br/>
            Status: <span style="color:${statusColor(status)};font-weight:600;">${escapeHtml(status)}</span><br/>
            Stop: ${escapeHtml(stopName)}<br/>
            Progress: ${progress.completed || 0}/${progress.total || 0}<br/>
            GPS: ${lat.toFixed(5)}, ${lng.toFixed(5)}
          </div>`;
        marker.bindPopup(popupHtml);

        marker.on('click', () => {
          DASH.state.selectAssignment(a.assignment_id);
        });

        vehicleMarkers[a.assignment_id] = marker;
      });
    },

    updateStops(stops, currentStopId) {
      if (!mapInstance) return;
      stopMarkerLayer.clearLayers();

      if (!stops || stops.length === 0) return;

      stops.forEach((s) => {
        if (!s.lat || !s.lng) return;
        const lat = parseFloat(s.lat);
        const lng = parseFloat(s.lng);
        if (isNaN(lat) || isNaN(lng)) return;

        const execStatus = s.execution_status || 'planned';
        const isCurrent = currentStopId && s.id === currentStopId;
        const cssClass = isCurrent ? 'stop-marker-icon current' : 'stop-marker-icon ' + execStatus;

        const icon = L.divIcon({
          className: '',
          html: `<div class="${cssClass}" title="${escapeHtml(s.station_name || 'Stop')}"></div>`,
          iconSize: [14, 14],
          iconAnchor: [7, 7],
        });

        const marker = L.marker([lat, lng], { icon }).addTo(stopMarkerLayer);
        const popupHtml = `
          <div style="font-size:12px;min-width:160px;">
            <strong>#${s.planned_sequence} ${escapeHtml(s.station_name || '')}</strong><br/>
            ${s.station_code ? 'Code: ' + escapeHtml(s.station_code) + '<br/>' : ''}
            Status: <span style="font-weight:600;">${escapeHtml(execStatus)}</span><br/>
            ${s.product_description ? 'Product: ' + escapeHtml(s.product_description) + '<br/>' : ''}
            ${s.manager_name ? 'Contact: ' + escapeHtml(s.manager_name) + '<br/>' : ''}
          </div>`;
        marker.bindPopup(popupHtml);
      });
    },

    updateRoute(stops) {
      if (!mapInstance) return;
      routeLayer.clearLayers();

      if (!stops || stops.length < 2) return;

      const coords = [];
      stops.forEach((s) => {
        if (s.lat && s.lng) {
          const lat = parseFloat(s.lat);
          const lng = parseFloat(s.lng);
          if (!isNaN(lat) && !isNaN(lng)) {
            coords.push([lat, lng]);
          }
        }
      });

      if (coords.length < 2) return;

      const polyline = L.polyline(coords, {
        color: '#388bfd',
        weight: 3,
        opacity: 0.6,
        dashArray: '8, 8',
      }).addTo(routeLayer);
    },

    zoomToVehicle(assignmentId) {
      const marker = vehicleMarkers[assignmentId];
      if (marker && mapInstance) {
        mapInstance.setView(marker.getLatLng(), 14);
        marker.openPopup();
        currentZoomAssignment = assignmentId;
      }
    },

    zoomToAll() {
      if (!mapInstance) return;
      const allMarkers = Object.values(vehicleMarkers);
      if (allMarkers.length === 0) return;
      const group = L.featureGroup(allMarkers);
      mapInstance.fitBounds(group.getBounds().pad(0.1));
    },

    openGoogleMaps(assignmentId, stops) {
      const marker = vehicleMarkers[assignmentId];
      if (!marker) return;
      const latlng = marker.getLatLng();
      const query = stops && stops.length > 0
        ? stops.map(s => `${s.lat},${s.lng}`).join('/')
        : `${latlng.lat},${latlng.lng}`;
      window.open(`https://www.google.com/maps/dir/${latlng.lat},${latlng.lng}/${query}`, '_blank');
    },

    getMap() { return mapInstance; },

    invalidateSize() {
      if (mapInstance) setTimeout(() => mapInstance.invalidateSize(), 100);
    },
  };
})();
