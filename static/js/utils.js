
// Toast notification utilities
let toastContainer;

function initToasts() {
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container';
        document.body.appendChild(toastContainer);
    }
}

function showToast(message, type = 'info', duration = 3000) {
    initToasts();

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => {
            if (toastContainer.contains(toast)) {
                toastContainer.removeChild(toast);
            }
        }, 300);
    }, duration);
}

/**
 * Calculate centroid of a single polygon
 * @param {Array<Array<number>>} polygon - Array of [lat, lng] points
 * @returns {Array<number>|null} Centroid as [lat, lng], or null if invalid
 */
function calculatePolygonCentroid(polygon) {
    if (!polygon || polygon.length < 3) {
        return null;
    }

    // Ensure polygon is closed
    const closedPolygon = [...polygon, polygon[0]];
    let signedArea = 0;
    let sumLat = 0;
    let sumLng = 0;

    for (let i = 0; i < closedPolygon.length - 1; i++) {
        const [latI, lngI] = closedPolygon[i];
        const [latJ, lngJ] = closedPolygon[i + 1];
        const term = (latI * lngJ) - (latJ * lngI);
        signedArea += term;
        sumLat += (latI + latJ) * term;
        sumLng += (lngI + lngJ) * term;
    }

    signedArea /= 2;

    if (Math.abs(signedArea) < 1e-10) {
        // Degenerate polygon, return average of vertices
        const avgLat = polygon.reduce((sum, p) => sum + p[0], 0) / polygon.length;
        const avgLng = polygon.reduce((sum, p) => sum + p[1], 0) / polygon.length;
        return [avgLat, avgLng];
    }

    const centroidLat = sumLat / (6 * signedArea);
    const centroidLng = sumLng / (6 * signedArea);
    return [centroidLat, centroidLng];
}

/**
 * Calculate centroid of a multi-polygon (multiple polygons)
 * Returns weighted average of all polygon centroids
 * @param {Array<Array<Array<number>>>} polygons - Array of polygons, each is array of [lat, lng]
 * @returns {Array<number>|null} Centroid as [lat, lng], or null if invalid
 */
function calculateMultiPolygonCentroid(polygons) {
    if (!polygons || !Array.isArray(polygons) || polygons.length === 0) {
        return null;
    }

    const centroids = [];
    const areas = [];

    for (const polygon of polygons) {
        const centroid = calculatePolygonCentroid(polygon);
        if (centroid) {
            centroids.push(centroid);
            // Calculate area for weighting
            let area = 0;
            const closedPoly = [...polygon, polygon[0]];
            for (let i = 0; i < closedPoly.length - 1; i++) {
                const [latI, lngI] = closedPoly[i];
                const [latJ, lngJ] = closedPoly[i + 1];
                area += (latI * lngJ) - (latJ * lngI);
            }
            areas.push(Math.abs(area / 2));
        }
    }

    if (centroids.length === 0) {
        return null;
    }

    const totalArea = areas.reduce((sum, a) => sum + a, 0);
    if (totalArea === 0) {
        // All degenerate, just average centroids
        const avgLat = centroids.reduce((sum, c) => sum + c[0], 0) / centroids.length;
        const avgLng = centroids.reduce((sum, c) => sum + c[1], 0) / centroids.length;
        return [avgLat, avgLng];
    }

    let weightedLat = 0;
    let weightedLng = 0;
    for (let i = 0; i < centroids.length; i++) {
        const weight = areas[i] / totalArea;
        weightedLat += centroids[i][0] * weight;
        weightedLng += centroids[i][1] * weight;
    }

    return [weightedLat, weightedLng];
}

/**
 * Get centroid from a location object (handles single polygon, multi-polygon, or point)
 * @param {Object} location - Location object with polygons, corners, or lat/lng
 * @returns {Object|null} { lat: number, lng: number }
 */
function getLocationCentroid(location) {
    if (!location) return null;
    if (location.polygons && Array.isArray(location.polygons)) {
        const centroid = calculateMultiPolygonCentroid(location.polygons);
        if (centroid) return { lat: centroid[0], lng: centroid[1] };
    }
    if (location.corners && Array.isArray(location.corners)) {
        const centroid = calculatePolygonCentroid(location.corners);
        if (centroid) return { lat: centroid[0], lng: centroid[1] };
    }
    if (location.latitude !== undefined && location.longitude !== undefined) {
        return { lat: location.latitude, lng: location.longitude };
    }
    return null;
}

/**
 * Check if a point is inside a polygon or multi-polygon using Ray Casting algorithm
 * @param {number} lat - Point latitude
 * @param {number} lng - Point longitude
 * @param {Object} location - Location object with polygons or corners
 * @returns {boolean} True if point is inside the location's polygon(s)
 */
function isPointInLocation(lat, lng, location) {
    if (!location) return false;
    let polygonsToCheck = [];
    if (location.polygons && Array.isArray(location.polygons)) {
        polygonsToCheck = location.polygons;
    } else if (location.corners && Array.isArray(location.corners)) {
        polygonsToCheck = [location.corners];
    } else if (location.latitude !== undefined && location.longitude !== undefined) {
        const distance = getDistanceMeters(
            location.latitude, location.longitude,
            lat, lng
        );
        const locRadius = (location.radius_km || 3) * 1000;
        return distance <= locRadius;
    } else {
        return false;
    }
    
    for (const polygon of polygonsToCheck) {
        if (isPointInPolygon(lat, lng, polygon)) {
            return true;
        }
    }
    return false;
}

function getDistanceMeters(lat1, lon1, lat2, lon2) {
    const toRad = (deg) => (deg * Math.PI) / 180;
    const R = 6371000;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) ** 2 +
        Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

/**
 * Check if a point is inside a single polygon using Ray Casting algorithm
 * @param {number} lat - Point latitude
 * @param {number} lng - Point longitude
 * @param {Array<Array<number>>} polygon - Polygon as array of [lat, lng]
 * @returns {boolean} True if point is inside polygon
 */
function isPointInPolygon(lat, lng, polygon) {
    if (!polygon || polygon.length < 3) {
        return false;
    }
    let inside = false;
    const n = polygon.length;
    let x = lng;
    let y = lat;
    for (let i = 0, j = n - 1; i < n; j = i++) {
        const xi = polygon[i][1];
        const yi = polygon[i][0];
        const xj = polygon[j][1];
        const yj = polygon[j][0];
        
        const intersect = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
        if (intersect) {
            inside = !inside;
        }
    }
    return inside;
}

/**
 * Normalize Vietnamese text to remove diacritics and convert to lowercase
 * @param {string} value - Text to normalize
 * @returns {string} Normalized text
 */
function normalizeText(value) {
    return String(value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/đ/g, "d")
        .replace(/Đ/g, "D")
        .toLowerCase();
}

