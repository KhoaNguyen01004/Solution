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
  let vehicleMarkers = {}; // assignment_id → { marker, labelEl, label, borderColor, lat, lng, popupHtml }
  let currentZoomAssignment = null;

  let stopMarkers = new Map(); // stop_id → { marker, iconEl, cssClass, popupHtml }
  let stopsSetKey = null; // join of stop ids currently rendered — detects assignment switch vs. same-set poll
  let lastRouteKey = null; // join of route coords — skips redundant polyline rebuilds

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
      planned: '#9ca3af',
      skipped: '#eab308',
      cancelled: '#ef4444',
    };
    return map[status] || '#9ca3af';
  }

  function vehiclePopupHtml(a, label, status, lat, lng) {
    const stopName = a.current_stop ? (a.current_stop.station_name || a.current_stop.station_code || 'Stop #' + a.current_stop.planned_sequence) : 'No active stop';
    const progress = a.progress || {};
    return `
          <div style="font-size:12px;min-width:160px;">
            <strong>${escapeHtml(label)}</strong><br/>
            Driver: ${escapeHtml(a.current_driver || 'N/A')}<br/>
            Status: <span style="color:${statusColor(status)};font-weight:600;">${escapeHtml(status)}</span><br/>
            Stop: ${escapeHtml(stopName)}<br/>
            Progress: ${progress.completed || 0}/${progress.total || 0}<br/>
            GPS: ${lat.toFixed(5)}, ${lng.toFixed(5)}
          </div>`;
  }

  function stopPopupHtml(s, execStatus) {
    return `
          <div style="font-size:12px;min-width:160px;">
            <strong>#${s.planned_sequence} ${escapeHtml(s.station_name || '')}</strong><br/>
            ${s.station_code ? 'Code: ' + escapeHtml(s.station_code) + '<br/>' : ''}
            Status: <span style="font-weight:600;">${escapeHtml(execStatus)}</span><br/>
            ${s.product_description ? 'Product: ' + escapeHtml(s.product_description) + '<br/>' : ''}
            ${s.manager_name ? 'Contact: ' + escapeHtml(s.manager_name) + '<br/>' : ''}
          </div>`;
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

    // Diffs against the previously-rendered vehicle markers instead of
    // clearLayers()+recreate every poll — preserves marker identity, any
    // open popup, and avoids rebinding click handlers every 12s.
    updateVehicles(assignments) {
      if (!mapInstance) return;
      const seen = new Set();

      (assignments || []).forEach((a) => {
        const gps = a.gps;
        if (!gps || gps.lat == null || gps.lng == null) return;
        const lat = parseFloat(gps.lat);
        const lng = parseFloat(gps.lng);
        if (isNaN(lat) || isNaN(lng)) return;

        seen.add(a.assignment_id);

        const isSelected = a.assignment_id === DASH.state.selectedAssignmentId;
        const label = a.plate_number || 'V' + a.assignment_id;
        const status = a.plan_status || 'confirmed';
        const borderColor = isSelected ? '#fb923c' : statusColor(status);
        const popupHtml = vehiclePopupHtml(a, label, status, lat, lng);

        let entry = vehicleMarkers[a.assignment_id];
        if (!entry) {
          const icon = L.divIcon({
            className: '',
            html: `<div class="vehicle-marker-label" style="border-color:${borderColor};">${escapeHtml(label)}</div>`,
            iconSize: [0, 0],
            iconAnchor: [0, 0],
          });
          const marker = L.marker([lat, lng], { icon }).addTo(vehicleMarkerLayer);
          marker.bindPopup(popupHtml);
          marker.on('click', () => {
            DASH.state.selectAssignment(a.assignment_id);
          });
          const el = marker.getElement();
          const labelEl = el ? el.querySelector('.vehicle-marker-label') : null;
          vehicleMarkers[a.assignment_id] = { marker, labelEl, label, borderColor, lat, lng, popupHtml };
          return;
        }

        if (entry.lat !== lat || entry.lng !== lng) {
          entry.marker.setLatLng([lat, lng]);
          entry.lat = lat;
          entry.lng = lng;
        }

        if (entry.label !== label || entry.borderColor !== borderColor) {
          if (entry.labelEl) {
            entry.labelEl.textContent = label;
            entry.labelEl.style.borderColor = borderColor;
          }
          entry.label = label;
          entry.borderColor = borderColor;
        }

        if (entry.popupHtml !== popupHtml) {
          const popup = entry.marker.getPopup();
          if (popup) popup.setContent(popupHtml);
          entry.popupHtml = popupHtml;
        }
      });

      // Remove markers for assignments no longer in the list (filtered out, completed, etc.)
      Object.keys(vehicleMarkers).forEach((key) => {
        if (!seen.has(Number(key))) {
          vehicleMarkerLayer.removeLayer(vehicleMarkers[key].marker);
          delete vehicleMarkers[key];
        }
      });
    },

    // Full rebuild only when the set of stop ids changes (assignment
    // switched, or a stop was inserted/removed); a same-assignment poll
    // only patches status/current-marker/popup on existing markers.
    updateStops(stops, currentStopId) {
      if (!mapInstance) return;
      const list = stops || [];
      const key = list.map((s) => s.id).join(',');

      if (key !== stopsSetKey) {
        stopMarkerLayer.clearLayers();
        stopMarkers.clear();
        stopsSetKey = key;

        list.forEach((s) => {
          if (!s.lat || !s.lng) return;
          const lat = parseFloat(s.lat);
          const lng = parseFloat(s.lng);
          if (isNaN(lat) || isNaN(lng)) return;

          const execStatus = s.execution_status || 'planned';
          const isCurrent = currentStopId && s.id === currentStopId;
          const cssClass = isCurrent ? 'stop-marker-icon current' : 'stop-marker-icon ' + execStatus;
          const popupHtml = stopPopupHtml(s, execStatus);

          const icon = L.divIcon({
            className: '',
            html: `<div class="${cssClass}" title="${escapeHtml(s.station_name || 'Stop')}"></div>`,
            iconSize: [14, 14],
            iconAnchor: [7, 7],
          });
          const marker = L.marker([lat, lng], { icon }).addTo(stopMarkerLayer);
          marker.bindPopup(popupHtml);
          const el = marker.getElement();
          const iconEl = el ? el.querySelector('.stop-marker-icon') : null;
          stopMarkers.set(s.id, { marker, iconEl, cssClass, popupHtml });
        });
        return;
      }

      list.forEach((s) => {
        const entry = stopMarkers.get(s.id);
        if (!entry) return; // stop had no coords originally, nothing to patch

        const execStatus = s.execution_status || 'planned';
        const isCurrent = currentStopId && s.id === currentStopId;
        const cssClass = isCurrent ? 'stop-marker-icon current' : 'stop-marker-icon ' + execStatus;
        const popupHtml = stopPopupHtml(s, execStatus);

        if (entry.cssClass !== cssClass) {
          if (entry.iconEl) entry.iconEl.className = cssClass;
          entry.cssClass = cssClass;
        }
        if (entry.popupHtml !== popupHtml) {
          const popup = entry.marker.getPopup();
          if (popup) popup.setContent(popupHtml);
          entry.popupHtml = popupHtml;
        }
      });
    },

    // Draws the actual road route from /api/eta's per-leg ORS geometry
    // instead of a straight line through stop coordinates. Falls back to a
    // straight segment only for legs where road geometry wasn't available
    // (no ORS key, or that leg fell back to haversine), and to the old
    // all-stops straight line only when there's no live ETA/GPS at all.
    // Skips the rebuild entirely when the resulting path hasn't changed.
    updateRoute(eta, stops) {
      if (!mapInstance) return;

      const legs = (eta && eta.etas) || [];
      let coords = [];
      let usedRoadGeometry = false;

      if (legs.length > 0) {
        let prevLat = eta.gps ? eta.gps.lat : null;
        let prevLng = eta.gps ? eta.gps.lng : null;

        legs.forEach((leg) => {
          if (leg.geometry && leg.geometry.length > 0) {
            coords = coords.concat(leg.geometry);
            usedRoadGeometry = true;
          } else if (prevLat != null && prevLng != null && leg.lat != null && leg.lng != null) {
            coords.push([prevLat, prevLng], [parseFloat(leg.lat), parseFloat(leg.lng)]);
          }
          if (leg.lat != null && leg.lng != null) {
            prevLat = parseFloat(leg.lat);
            prevLng = parseFloat(leg.lng);
          }
        });
      } else {
        // No live ETA available (GPS offline, etc.) — preserve the old
        // straight-line-through-all-stops behavior rather than showing nothing.
        (stops || []).forEach((s) => {
          if (s.lat && s.lng) {
            const lat = parseFloat(s.lat);
            const lng = parseFloat(s.lng);
            if (!isNaN(lat) && !isNaN(lng)) coords.push([lat, lng]);
          }
        });
      }

      const key = coords.map((c) => c[0] + ',' + c[1]).join('|');
      if (key === lastRouteKey) return;
      lastRouteKey = key;

      routeLayer.clearLayers();
      if (coords.length < 2) return;

      L.polyline(coords, {
        color: '#388bfd',
        weight: 3,
        opacity: 0.7,
        dashArray: usedRoadGeometry ? '' : '8, 8',
      }).addTo(routeLayer);
    },

    zoomToVehicle(assignmentId) {
      const entry = vehicleMarkers[assignmentId];
      if (entry && mapInstance) {
        mapInstance.setView(entry.marker.getLatLng(), 14);
        entry.marker.openPopup();
        currentZoomAssignment = assignmentId;
      }
    },

    // Re-centers on the vehicle without forcing zoom or popping its popup
    // open — used every poll while "Follow" is active, so it stays gentle
    // rather than fighting a dispatcher who's manually zoomed/panned.
    followVehicle(assignmentId) {
      const entry = vehicleMarkers[assignmentId];
      if (entry && mapInstance) {
        mapInstance.panTo(entry.marker.getLatLng());
      }
    },

    zoomToAll() {
      if (!mapInstance) return;
      const allMarkers = Object.values(vehicleMarkers).map((e) => e.marker);
      if (allMarkers.length === 0) return;
      const group = L.featureGroup(allMarkers);
      mapInstance.fitBounds(group.getBounds().pad(0.1));
    },

    openGoogleMaps(assignmentId, stops) {
      const entry = vehicleMarkers[assignmentId];
      if (!entry) return;
      const latlng = entry.marker.getLatLng();
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
