/**
 * SafeHer — Women Safety Route Navigation Application
 * Main Application Logic & Interactive Leaflet Controller
 */

// Backend Flask API base URL configuration (supports both direct Flask serving & standalone frontend)
const API_BASE_URL = window.location.origin.includes('5000') 
  ? '' 
  : 'http://127.0.0.1:5000';

/**
 * Standard SafeHer API Error Class
 */
class ApiError extends Error {
  constructor(message, status = 0, errorCode = 'NETWORK_ERROR', details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errorCode = errorCode;
    this.details = details;
  }
}

/**
 * Reusable SafeHer API Request Function
 * Features:
 * - Uses AbortController for reliable request timeout (default 8000ms)
 * - Detects and handles network loss / offline states / backend unavailable
 * - Handles HTTP status codes: 400, 401, 403, 404, 500, 503
 * - Safely handles invalid or non-JSON payloads without crashing
 * - Returns structured error messages and error codes
 */
async function apiRequest(endpoint, options = {}) {
  const {
    timeout = 8000,
    headers = {},
    ...customOptions
  } = options;

  const url = (endpoint.startsWith('http://') || endpoint.startsWith('https://'))
    ? endpoint
    : `${API_BASE_URL}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  let response;
  try {
    response = await fetch(url, {
      ...customOptions,
      headers: {
        'Accept': 'application/json',
        ...(customOptions.body ? { 'Content-Type': 'application/json' } : {}),
        ...headers
      },
      signal: controller.signal
    });
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new ApiError('Request timed out. SafeHer server took too long to respond.', 408, 'REQUEST_TIMEOUT');
    }
    // Network offline or server unreachable
    throw new ApiError('Unable to connect to SafeHer server. Backend service is currently unavailable.', 0, 'BACKEND_UNAVAILABLE');
  } finally {
    clearTimeout(timeoutId);
  }

  // Parse response as JSON safely
  let responseData = null;
  const contentType = response.headers.get('content-type') || '';
  const textBody = await response.text().catch(() => '');

  if (contentType.includes('application/json') || (textBody && (textBody.trim().startsWith('{') || textBody.trim().startsWith('[')))) {
    try {
      responseData = JSON.parse(textBody);
    } catch (parseErr) {
      responseData = null;
    }
  }

  // Handle non-OK HTTP status codes (400, 401, 403, 404, 500, 503, etc.)
  if (!response.ok) {
    const status = response.status;
    let errorCode = (responseData && responseData.error_code) || '';
    let errorMessage = (responseData && responseData.message) || '';

    // Standardized status code mappings
    switch (status) {
      case 400:
        if (!errorCode) errorCode = 'BAD_REQUEST';
        if (!errorMessage) errorMessage = 'Invalid request parameters or format.';
        break;
      case 401:
        if (!errorCode) errorCode = 'UNAUTHORIZED';
        if (!errorMessage) errorMessage = 'Authentication required to access this resource.';
        break;
      case 403:
        if (!errorCode) errorCode = 'FORBIDDEN';
        if (!errorMessage) errorMessage = 'Access forbidden. You do not have permission.';
        break;
      case 404:
        if (!errorCode) errorCode = 'NOT_FOUND';
        if (!errorMessage) errorMessage = 'Requested SafeHer resource or endpoint was not found.';
        break;
      case 500:
        if (!errorCode) errorCode = 'INTERNAL_ERROR';
        if (!errorMessage) errorMessage = 'SafeHer internal server error. Please try again later.';
        break;
      case 503:
        if (!errorCode) errorCode = 'SERVICE_UNAVAILABLE';
        if (!errorMessage) errorMessage = 'SafeHer backend service is temporarily unavailable.';
        break;
      default:
        if (!errorCode) errorCode = 'HTTP_ERROR';
        if (!errorMessage) errorMessage = `Request failed with HTTP status ${status}.`;
        break;
    }

    throw new ApiError(errorMessage, status, errorCode, responseData);
  }

  // 2xx response but invalid JSON returned when body is not empty
  if (responseData === null && textBody && textBody.trim().length > 0) {
    throw new ApiError('Invalid JSON response received from server.', response.status, 'INVALID_JSON');
  }

  return responseData;
}

// Expose globally for testing and interactive use
window.ApiError = ApiError;
window.apiRequest = apiRequest;

// Pre-configured Verified Safe Landmarks & Transit Hubs (Offline & Fast Lookup)
const KNOWN_LOCATIONS = [
  { name: 'Metro Station Central, Gate 3', coords: [28.6328, 77.2155], icon: '🚇', type: 'Metro Transit Hub (Lit)' },
  { name: 'Greenfield Heights, Sector 14', coords: [28.6435, 77.2340], icon: '🏢', type: 'Residential Gated Complex' },
  { name: 'Connaught Place Inner Circle', coords: [28.6315, 77.2167], icon: '🛍️', type: 'Commercial Area (24/7 Patrol)' },
  { name: 'India Gate Central Lawns', coords: [28.6129, 77.2295], icon: '🏛️', type: 'High Security National Zone' },
  { name: 'Saket City Centre Mall', coords: [28.5283, 77.2192], icon: '🛡️', type: 'Safe Commercial Avenue' },
  { name: 'Hauz Khas Village Main Gate', coords: [28.5539, 77.1942], icon: '📍', type: 'Active Commercial Zone' },
  { name: 'Karol Bagh Metro Gate 1', coords: [28.6517, 77.1906], icon: '🚇', type: 'Active Shopping Avenue' },
  { name: 'Dwarka Sector 21 Hub', coords: [28.5523, 77.0583], icon: '🚆', type: 'Interchange Transit Station' }
];

// Route Definitions with Detailed Safety Data (initial defaults with dynamic backend sync)
let ROUTES = [
  {
    id: 'route-safest',
    name: 'Main Boulevard Safe Corridor',
    shortName: 'Boulevard (Safest)',
    type: 'safest',
    score: 94,
    scoreColor: 'green',
    tier: 'SAFEST RECOMMENDED ROUTE',
    time: '14 min',
    distance: '3.2 km',
    desc: 'Optimal continuous LED street lighting, active pedestrian foot traffic, open 24/7 stores, and two active police outposts.',
    lighting: {
      val: '96% Lit',
      percent: 96,
      sub: 'Continuous high-intensity LED illumination',
      status: 'green'
    },
    crime: {
      val: 'Very Low',
      percent: 12,
      sub: 'Zero violent incidents recorded in 180 days',
      status: 'green'
    },
    crowd: {
      val: 'High Activity',
      percent: 92,
      sub: 'Open 24/7 pharmacies, cafes, & bus interchanges',
      status: 'green'
    },
    police: {
      val: '2 Booths (150m)',
      percent: 95,
      sub: 'Patrol response estimated within 90 seconds',
      status: 'green'
    },
    recommendation: 'Recommended: Keeps you on wide avenues with high visibility.',
    coordinates: [
      [28.6328, 77.2155], // Start: Central Metro
      [28.6342, 77.2185],
      [28.6360, 77.2220], // Main Boulevard
      [28.6375, 77.2260],
      [28.6385, 77.2305],
      [28.6410, 77.2325],
      [28.6435, 77.2340], // Greenfield Heights Dest
    ],
    turns: [
      { action: 'Start on Metro Plaza Walkway', dist: '100 m', safety: '🛡️ Safe Zone (24/7 Security Cameras)' },
      { action: 'Turn right onto Grand Boulevard', dist: '180 m', safety: '💡 100% LED Illuminated Corridor' },
      { action: 'Continue past Central City Police Station', dist: '650 m', safety: '👮 Police Booth within 60 meters' },
      { action: 'Pass open Late-Night Pharmacy & Market', dist: '1.2 km', safety: '👥 High Foot Traffic Area' },
      { action: 'Arrive at Greenfield Heights, Gate 2', dist: 'Destination', safety: '🛡️ Verified Safe Residence Arrival' }
    ]
  },
  {
    id: 'route-transit',
    name: 'Metro Avenue & Transit Link',
    shortName: 'Transit Ave (Fastest)',
    type: 'moderate',
    score: 76,
    scoreColor: 'amber',
    tier: 'MODERATE SAFETY ROUTE',
    time: '10 min',
    distance: '2.7 km',
    desc: 'Faster transit road along metro pillars. Well-trafficked until 10:30 PM, with some quiet pedestrian sidewalk stretches.',
    lighting: {
      val: '72% Lit',
      percent: 72,
      sub: 'Standard lamps with some tree cover shadows',
      status: 'amber'
    },
    crime: {
      val: 'Moderate',
      percent: 45,
      sub: 'Sporadic petty theft / phone snatching reports',
      status: 'amber'
    },
    crowd: {
      val: 'Moderate',
      percent: 65,
      sub: 'Bustling near stations, quiet side walks',
      status: 'amber'
    },
    police: {
      val: '1 Station (650m)',
      percent: 60,
      sub: 'Metro security desk at Sector 12 interchange',
      status: 'amber'
    },
    recommendation: 'Caution: Suitable during daylight or rush hours.',
    coordinates: [
      [28.6328, 77.2155], // Start
      [28.6350, 77.2170],
      [28.6380, 77.2210],
      [28.6395, 77.2270],
      [28.6435, 77.2340]  // Dest
    ],
    turns: [
      { action: 'Head east along Metro Viaduct', dist: '300 m', safety: '💡 Moderate Street Lighting' },
      { action: 'Turn onto Transit Link Rd', dist: '500 m', safety: '⚠️ Quiet pedestrian stretch' },
      { action: 'Reach Greenfield Heights', dist: 'Destination', safety: '🛡️ Arrival' }
    ]
  },
  {
    id: 'route-alley',
    name: 'Old Canal Alleyway Shortcut',
    shortName: 'Old Alley (Risky)',
    type: 'risky',
    score: 42,
    scoreColor: 'red',
    tier: 'HIGH RISK — NOT RECOMMENDED',
    time: '8 min',
    distance: '2.1 km',
    desc: 'Shortcut cutting through unmonitored back alleys and empty service lanes. Frequent non-functioning streetlights.',
    lighting: {
      val: '28% Lit',
      percent: 28,
      sub: 'Several broken streetlights & dark corners',
      status: 'red'
    },
    crime: {
      val: 'Elevated Risk',
      percent: 85,
      sub: 'Multiple incidents reported after dark',
      status: 'red'
    },
    crowd: {
      val: 'Isolated Area',
      percent: 18,
      sub: 'Closed shutters, deserted industrial alleyway',
      status: 'red'
    },
    police: {
      val: 'No Outpost (>1.8km)',
      percent: 15,
      sub: 'Emergency patrol response exceeds 12 mins',
      status: 'red'
    },
    recommendation: 'Warning: Not safe for solo walking at night.',
    coordinates: [
      [28.6328, 77.2155], // Start
      [28.6348, 77.2140],
      [28.6390, 77.2180], // Canal back lane
      [28.6415, 77.2250],
      [28.6435, 77.2340]  // Dest
    ],
    turns: [
      { action: 'Enter narrow canal access path', dist: '150 m', safety: '⚠️ Unlit Alleyway' },
      { action: 'Pass unmonitored rail underpass', dist: '400 m', safety: '⚠️ High incident blind spot' },
      { action: 'Exit into Sector 14 Gate', dist: 'Destination', safety: '🛡️ Arrival' }
    ]
  }
];

// Safety Zones (Safe green circles and Risky red circles)
let SAFETY_ZONES = [
  {
    lat: 28.6365,
    lng: 77.2240,
    radius: 420,
    type: 'safe',
    title: 'Grand Boulevard Commercial Corridor',
    desc: 'High foot traffic, 24/7 supermarkets, LED lighting & active security guards.'
  },
  {
    lat: 28.6330,
    lng: 77.2160,
    radius: 280,
    type: 'safe',
    title: 'Central Metro Hub',
    desc: 'Active CCTV coverage, transit security & continuous public presence.'
  },
  {
    lat: 28.6430,
    lng: 77.2330,
    radius: 300,
    type: 'safe',
    title: 'Sector 14 Residential Watch',
    desc: 'Gated community area with manned security checkpoints.'
  },
  {
    lat: 28.6385,
    lng: 77.2175,
    radius: 350,
    type: 'risky',
    title: 'Canal Back Alleyway',
    desc: 'Reported poor lighting, limited visibility, and isolated after 9 PM.'
  },
  {
    lat: 28.6405,
    lng: 77.2230,
    radius: 260,
    type: 'risky',
    title: 'Industrial Underpass Stretch',
    desc: 'Blind turns, closed warehouses, and absence of police surveillance.'
  }
];

// Police Stations & Safe Havens
let POLICE_LOCATIONS = [
  {
    lat: 28.6370,
    lng: 77.2235,
    name: 'Police Assistance Booth #4',
    type: 'booth',
    phone: '112',
    desc: '24/7 Women Safety Help Desk • Officers on Duty: 3'
  },
  {
    lat: 28.6335,
    lng: 77.2180,
    name: 'Metro Security & Transit Police',
    type: 'station',
    phone: '112',
    desc: 'Quick Response Team (QRT) Station'
  },
  {
    lat: 28.6420,
    lng: 77.2310,
    name: 'Sector 14 Patrol Outpost',
    type: 'booth',
    phone: '112',
    desc: 'Patrol bike unit & emergency safe shelter'
  }
];

class SafeHerApp {
  constructor() {
    this.selectedRouteIndex = 0;
    this.map = null;
    this.routePolylines = [];
    this.zoneCircles = [];
    this.policeMarkers = [];
    this.userMarker = null;
    this.destMarker = null;
    this.navSimulationMarker = null;
    this.simulationStep = 0;
    this.isNavigating = false;
    this.soundAlertsEnabled = true;

    // Route Endpoints state
    this.startLocation = 'Metro Station Central, Gate 3';
    this.destLocation = 'Greenfield Heights, Sector 14';
    this.startCoords = [28.6328, 77.2155];
    this.destCoords = [28.6435, 77.2340];
    this.isBackendConnected = false;

    // Siren Audio Context
    this.audioCtx = null;
    this.sirenOsc = null;
    this.sirenInterval = null;
    this.isSirenPlaying = false;

    // SOS Countdown
    this.sosCountdownInterval = null;
    this.sosSecondsLeft = 3;

    // Emergency Contacts State
    this.emergencyContacts = [];
    this.pendingDeleteContactId = null;

    // Current Real GPS State (Used exclusively for Real Current GPS SOS)
    this.currentGps = {
      latitude: null,
      longitude: null,
      accuracy: null,
      timestamp: null
    };
    this.gpsWatchId = null;
    this.sosEmergencyMarker = null;

    // Layer state
    this.showSafetyZones = true;
    this.showPolice = true;

    this.init();
  }

  init() {
    this.initMap();
    this.renderRouteCards();
    this.updateSafetyScorecard(this.selectedRouteIndex);
    this.drawMapElements();
    this.bindEvents();
    this.setupLocationSuggestions();
    this.initBackendConnection();
  }

  // Update backend health UI indicators
  updateBackendHealthUI(isConnected) {
    this.isBackendConnected = isConnected;
    const badge = document.getElementById('backendHealthBadge');
    const statusText = document.getElementById('backendStatusText');
    const safetyStatusText = document.getElementById('safetyStatusText');
    const chatBadge = document.getElementById('chatBackendBadge');

    const label = isConnected ? '🟢 Backend Connected' : '🔴 Backend Offline';

    if (statusText) statusText.innerText = label;
    if (safetyStatusText) safetyStatusText.innerText = label;

    if (badge) {
      if (isConnected) {
        badge.classList.remove('offline');
        badge.title = 'SafeHer Backend: Connected & Active';
      } else {
        badge.classList.add('offline');
        badge.title = 'SafeHer Backend: Offline (Standalone safety protection active)';
      }
    }

    if (chatBadge) {
      if (isConnected) {
        chatBadge.innerText = '⚡ Live';
        chatBadge.classList.remove('offline');
      } else {
        chatBadge.innerText = '📴 Offline';
        chatBadge.classList.add('offline');
      }
    }
  }

  // Check backend server health status safely without crashing
  async checkBackendHealth(loadDataIfConnected = true) {
    try {
      const health = await apiRequest('/api/health', { timeout: 4000 });
      if (health && health.status === 'healthy') {
        const wasOffline = !this.isBackendConnected;
        this.updateBackendHealthUI(true);

        if (wasOffline || loadDataIfConnected) {
          console.log('✓ SafeHer Backend Connected:', health);
          // Safely fetch dynamic data without crashing if any sub-request fails
          await Promise.allSettled([
            this.fetchSafetyZones(),
            this.fetchPoliceStations(),
            this.fetchRoutes(),
            this.fetchEmergencyContacts()
          ]);
        }
      } else {
        this.updateBackendHealthUI(false);
      }
    } catch (err) {
      console.warn('SafeHer backend offline or unreachable:', err.message);
      this.updateBackendHealthUI(false);
    }
  }

  // Connect to Flask Backend REST APIs with periodic health monitoring
  async initBackendConnection() {
    await this.checkBackendHealth(true);

    // Periodic health check every 15s to automatically reflect server state changes
    if (!this.healthCheckInterval) {
      this.healthCheckInterval = setInterval(() => {
        this.checkBackendHealth(false);
      }, 15000);
    }
  }

  async fetchSafetyZones() {
    try {
      const result = await apiRequest('/api/safety-zones', { timeout: 5000 });
      if (result && result.status === 'success' && result.data && result.data.length > 0) {
        SAFETY_ZONES = result.data;
        this.drawSafetyZones();
      }
    } catch (err) {
      console.warn('Failed to fetch safety zones from backend, retaining local safety zones:', err.message);
    }
  }

  async fetchPoliceStations() {
    try {
      const result = await apiRequest('/api/police-stations', { timeout: 5000 });
      if (result && result.status === 'success' && result.data && result.data.length > 0) {
        POLICE_LOCATIONS = result.data;
        this.drawPoliceStations();
      }
    } catch (err) {
      console.warn('Failed to fetch police stations from backend, retaining local stations:', err.message);
    }
  }

  async fetchRoutes() {
    try {
      const result = await apiRequest('/api/routes', {
        method: 'POST',
        body: JSON.stringify({
          start: this.startLocation,
          destination: this.destLocation,
          start_coords: this.startCoords,
          dest_coords: this.destCoords,
          time_of_day: 'auto'
        }),
        timeout: 8000
      });

      if (result && result.status === 'success' && result.data && result.data.routes && result.data.routes.length > 0) {
        ROUTES = result.data.routes;
        this.selectedRouteIndex = 0;
        this.renderRouteCards();
        this.updateSafetyScorecard(0);
        this.drawMapElements();

        // Fit bounds to the safest route
        if (ROUTES[0] && ROUTES[0].coordinates) {
          const bounds = L.latLngBounds(ROUTES[0].coordinates);
          this.map.fitBounds(bounds, { padding: [80, 80] });
        }
      }
    } catch (err) {
      console.warn('Failed to calculate routes via backend, retaining current routes:', err.message);
    }
  }

  // Initialize Leaflet Map
  initMap() {
    // Center between start and destination
    const centerPoint = [28.6380, 77.2245];
    this.map = L.map('safetyMap', {
      zoomControl: true,
      attributionControl: true
    }).setView(centerPoint, 14);


    // OpenStreetMap tiles — completely free, no API key, no watermark
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(this.map);

    // Custom Current Location Marker (Pulse Effect)
    const startCoord = ROUTES[0].coordinates[0];
    const userPulseHtml = `
      <div class="user-pulse-marker">
        <div class="user-pulse-wave"></div>
        <div class="user-pulse-center"></div>
      </div>
    `;
    const userIcon = L.divIcon({
      html: userPulseHtml,
      className: 'custom-pulse-container',
      iconSize: [40, 40],
      iconAnchor: [20, 20]
    });
    this.userMarker = L.marker(startCoord, { icon: userIcon, draggable: true }).addTo(this.map);
    this.userMarker.bindPopup('<b>Current Location (Drag to adjust)</b><br>Metro Station Central, Gate 3');
    this.userMarker.on('dragend', async (e) => {
      const pos = e.target.getLatLng();
      this.startCoords = [pos.lat, pos.lng];
      const name = `Pinned Location (${pos.lat.toFixed(4)}, ${pos.lng.toFixed(4)})`;
      this.startLocation = name;
      const startInput = document.getElementById('startLocationInput');
      if (startInput) startInput.value = name;
      this.userMarker.setPopupContent(`<b>Start Location (Map Pin)</b><br>${name}`);
      this.showToast('📍 Start pin moved — recalculating safest routes...');
      this.fetchRoutes();
    });

    // Destination Marker
    const destCoord = ROUTES[0].coordinates[ROUTES[0].coordinates.length - 1];
    const destPinHtml = `
      <div class="dest-pin-marker">
        <div class="dest-pin-badge">🏁 Destination</div>
      </div>
    `;
    const destIcon = L.divIcon({
      html: destPinHtml,
      className: 'dest-pin-container',
      iconSize: [90, 28],
      iconAnchor: [45, 14]
    });
    this.destMarker = L.marker(destCoord, { icon: destIcon, draggable: true }).addTo(this.map);
    this.destMarker.bindPopup('<b>Destination (Drag to adjust)</b><br>Greenfield Heights, Sector 14');
    this.destMarker.on('dragend', async (e) => {
      const pos = e.target.getLatLng();
      this.destCoords = [pos.lat, pos.lng];
      const name = `Pinned Destination (${pos.lat.toFixed(4)}, ${pos.lng.toFixed(4)})`;
      this.destLocation = name;
      const destInput = document.getElementById('destLocationInput');
      if (destInput) destInput.value = name;
      this.destMarker.setPopupContent(`<b>Destination (Map Pin)</b><br>${name}`);
      this.showToast('🏁 Destination pin moved — recalculating safest routes...');
      this.fetchRoutes();
    });
  }

  // Draw Route Polylines, Safety Zones, and Police Stations
  drawMapElements() {
    // 1. Draw Routes
    this.routePolylines.forEach(layer => this.map.removeLayer(layer));
    this.routePolylines = [];

    ROUTES.forEach((route, index) => {
      const isSelected = index === this.selectedRouteIndex;
      let strokeColor = '#6B7280';
      let strokeWidth = 5;
      let strokeOpacity = 0.45;
      let dashArray = null;

      if (route.type === 'safest') {
        strokeColor = isSelected ? '#10B981' : '#059669';
        strokeWidth = isSelected ? 7 : 4;
        strokeOpacity = isSelected ? 0.95 : 0.45;
      } else if (route.type === 'moderate') {
        strokeColor = isSelected ? '#F59E0B' : '#D97706';
        strokeWidth = isSelected ? 6 : 4;
        strokeOpacity = isSelected ? 0.9 : 0.4;
      } else {
        strokeColor = isSelected ? '#EF4444' : '#DC2626';
        strokeWidth = isSelected ? 6 : 4;
        strokeOpacity = isSelected ? 0.9 : 0.4;
        dashArray = '6, 6';
      }

      // Outer Glow Polyline for Selected Route
      if (isSelected) {
        const glowLine = L.polyline(route.coordinates, {
          color: route.type === 'safest' ? '#34D399' : (route.type === 'moderate' ? '#FBBF24' : '#F87171'),
          weight: strokeWidth + 6,
          opacity: 0.35,
          lineCap: 'round',
          lineJoin: 'round'
        }).addTo(this.map);
        this.routePolylines.push(glowLine);
      }

      const polyline = L.polyline(route.coordinates, {
        color: strokeColor,
        weight: strokeWidth,
        opacity: strokeOpacity,
        dashArray: dashArray,
        lineCap: 'round',
        lineJoin: 'round',
        smoothFactor: 1
      }).addTo(this.map);

      polyline.on('click', () => {
        this.selectRoute(index);
      });

      this.routePolylines.push(polyline);
    });

    // 2. Draw Safety Zones (Green for Safe, Red for Risky)
    this.drawSafetyZones();

    // 3. Draw Police Stations
    this.drawPoliceStations();
  }

  drawSafetyZones() {
    this.zoneCircles.forEach(circle => this.map.removeLayer(circle));
    this.zoneCircles = [];

    if (!this.showSafetyZones) return;

    SAFETY_ZONES.forEach(zone => {
      const isSafe = zone.type === 'safe';
      const color = isSafe ? '#10B981' : '#EF4444';
      const fillColor = isSafe ? '#10B981' : '#EF4444';

      const circle = L.circle([zone.lat, zone.lng], {
        color: color,
        fillColor: fillColor,
        fillOpacity: isSafe ? 0.15 : 0.22,
        weight: 1.5,
        radius: zone.radius,
        dashArray: isSafe ? null : '4, 4'
      }).addTo(this.map);

      const popupHtml = `
        <div style="font-family: Inter, sans-serif; font-size: 12px; color: #111827;">
          <strong style="color: ${isSafe ? '#059669' : '#DC2626'}; display: flex; align-items: center; gap: 4px;">
            ${isSafe ? '🛡️ Safe Zone' : '⚠️ Low Light / Risky Zone'}
          </strong>
          <h4 style="margin: 4px 0 2px; font-size: 13px;">${zone.title}</h4>
          <p style="margin: 0; color: #4B5563; font-size: 11px;">${zone.desc}</p>
        </div>
      `;
      circle.bindPopup(popupHtml);
      this.zoneCircles.push(circle);
    });
  }

  drawPoliceStations() {
    this.policeMarkers.forEach(m => this.map.removeLayer(m));
    this.policeMarkers = [];

    if (!this.showPolice) return;

    POLICE_LOCATIONS.forEach(p => {
      const policePinHtml = `
        <div class="police-pin-marker" title="${p.name}">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
        </div>
      `;
      const icon = L.divIcon({
        html: policePinHtml,
        className: 'police-custom-icon',
        iconSize: [28, 28],
        iconAnchor: [14, 14]
      });

      const marker = L.marker([p.lat, p.lng], { icon: icon }).addTo(this.map);
      marker.bindPopup(`
        <div style="font-family: Inter, sans-serif; font-size: 12px; color: #111827;">
          <strong style="color: #1E40AF; display: flex; align-items: center; gap: 4px;">
            👮 Police Assistance Point
          </strong>
          <h4 style="margin: 4px 0 2px; font-size: 13px;">${p.name}</h4>
          <p style="margin: 0 0 6px; color: #4B5563; font-size: 11px;">${p.desc}</p>
          <a href="tel:${p.phone}" style="display: inline-block; background: #2563EB; color: white; padding: 3px 8px; border-radius: 4px; text-decoration: none; font-size: 11px; font-weight: 600;">
            Call Helpline 112
          </a>
        </div>
      `);
      this.policeMarkers.push(marker);
    });
  }

  // Render Route Cards
  renderRouteCards() {
    const container = document.getElementById('routesGrid');
    container.innerHTML = '';

    ROUTES.forEach((route, index) => {
      const isSelected = index === this.selectedRouteIndex;
      const card = document.createElement('div');
      card.className = `route-card ${isSelected ? 'active' : ''} is-${route.type}`;
      card.id = `routeCard-${index}`;

      let badgeClass = 'badge-safest';
      let badgeLabel = 'SAFEST';
      let scoreColorClass = 'score-green';

      if (route.type === 'moderate') {
        badgeClass = 'badge-moderate';
        badgeLabel = 'FASTER';
        scoreColorClass = 'score-amber';
      } else if (route.type === 'risky') {
        badgeClass = 'badge-risky';
        badgeLabel = 'RISKY';
        scoreColorClass = 'score-red';
      }

      const ml = route.ml_risk || null;
      const mlBadgeHtml = ml && ml.risk_label && ml.risk_label !== 'UNKNOWN' ? `
        <div class="ml-risk-badge" style="
          display: flex; align-items: center; gap: 6px;
          margin-top: 8px; padding: 5px 8px; border-radius: 6px;
          background: ${ml.color}18; border: 1px solid ${ml.color}44;
          font-size: 10.5px; font-weight: 600; color: ${ml.color};
          font-family: Inter, sans-serif;
        ">
          <span style="font-size: 13px;">${ml.icon}</span>
          <span>ML: ${ml.risk_label} RISK</span>
          <span style="margin-left: auto; font-size: 10px; opacity: 0.75;">${ml.confidence_pct}% confident</span>
        </div>` : '';

      card.innerHTML = `
        <div class="route-card-top">
          <span class="route-badge ${badgeClass}">${badgeLabel}</span>
          <span class="route-score-pill ${scoreColorClass}">★ ${route.score}/100</span>
        </div>
        <div class="route-name">${route.shortName}</div>
        <div class="route-meta">
          <span>⏱️ ${route.time}</span>
          <span>•</span>
          <span>📍 ${route.distance}</span>
        </div>
        <div class="route-safety-tagline" style="color: ${route.type === 'safest' ? 'var(--safe-green-light)' : (route.type === 'moderate' ? 'var(--moderate-amber)' : 'var(--risky-red-light)')}">
          <span>${route.type === 'safest' ? '🛡️ Best Lit' : (route.type === 'moderate' ? '⚠️ Quiet Areas' : '⛔ Dark Stretches')}</span>
        </div>
        ${mlBadgeHtml}
      `;


      card.addEventListener('click', () => {
        this.selectRoute(index);
      });

      container.appendChild(card);
    });
  }

  // Select Route & Update UI
  selectRoute(index) {
    this.selectedRouteIndex = index;

    // Update active card style
    ROUTES.forEach((_, i) => {
      const el = document.getElementById(`routeCard-${i}`);
      if (el) {
        if (i === index) {
          el.classList.add('active');
        } else {
          el.classList.remove('active');
        }
      }
    });

    this.updateSafetyScorecard(index);
    this.drawMapElements();

    // Smoothly pan & fit bounds for selected route
    const coords = ROUTES[index].coordinates;
    const bounds = L.latLngBounds(coords);
    this.map.fitBounds(bounds, { padding: [80, 80], maxZoom: 16 });
  }

  // Update Safety Breakdown Scorecard
  updateSafetyScorecard(index) {
    const route = ROUTES[index];

    // Score Number & Tier Badge
    const scoreNumEl = document.getElementById('scoreNumber');
    const scoreGauge = document.getElementById('scoreGauge');
    const tierBadge = document.getElementById('scoreTierBadge');
    const tierText = document.getElementById('scoreTierText');
    const titleEl = document.getElementById('selectedRouteTitle');
    const descEl = document.getElementById('selectedRouteDesc');
    const startBtn = document.getElementById('startSafeRouteBtn');
    const startBtnText = document.getElementById('startBtnText');

    scoreNumEl.innerText = route.score;
    titleEl.innerText = route.name;
    descEl.innerText = route.desc;
    tierText.innerText = route.tier;

    // Update gauge styling & Start button context
    if (route.type === 'safest') {
      scoreGauge.style.borderColor = 'var(--safe-green)';
      scoreGauge.style.boxShadow = '0 0 16px var(--safe-green-glow)';
      tierBadge.style.color = 'var(--safe-green-light)';
      startBtn.style.background = 'linear-gradient(135deg, #10B981, #059669)';
      startBtn.style.boxShadow = '0 4px 18px rgba(16, 185, 129, 0.45)';
      startBtnText.innerText = 'Start Safe Route';
    } else if (route.type === 'moderate') {
      scoreGauge.style.borderColor = 'var(--moderate-amber)';
      scoreGauge.style.boxShadow = '0 0 16px rgba(245, 158, 11, 0.4)';
      tierBadge.style.color = 'var(--moderate-amber)';
      startBtn.style.background = 'linear-gradient(135deg, #F59E0B, #D97706)';
      startBtn.style.boxShadow = '0 4px 18px rgba(245, 158, 11, 0.4)';
      startBtnText.innerText = 'Proceed with Caution';
    } else {
      scoreGauge.style.borderColor = 'var(--risky-red)';
      scoreGauge.style.boxShadow = '0 0 16px var(--risky-red-glow)';
      tierBadge.style.color = 'var(--risky-red-light)';
      startBtn.style.background = 'linear-gradient(135deg, #DC2626, #B91C1C)';
      startBtn.style.boxShadow = '0 4px 18px rgba(220, 38, 38, 0.45)';
      startBtnText.innerText = 'Risky Route (Switch to Safe)';
    }

    // Factor: Street Lighting
    document.getElementById('valLighting').innerText = route.lighting.val;
    document.getElementById('subLighting').innerText = route.lighting.sub;
    const barLighting = document.getElementById('barLighting');
    barLighting.style.width = `${route.lighting.percent}%`;
    barLighting.className = `meter-fill fill-${route.lighting.status}`;

    // Factor: Crime Level
    document.getElementById('valCrime').innerText = route.crime.val;
    document.getElementById('subCrime').innerText = route.crime.sub;
    const barCrime = document.getElementById('barCrime');
    barCrime.style.width = `${route.crime.percent}%`;
    barCrime.className = `meter-fill fill-${route.crime.status}`;

    // Factor: Crowd Activity
    document.getElementById('valCrowd').innerText = route.crowd.val;
    document.getElementById('subCrowd').innerText = route.crowd.sub;
    const barCrowd = document.getElementById('barCrowd');
    barCrowd.style.width = `${route.crowd.percent}%`;
    barCrowd.className = `meter-fill fill-${route.crowd.status}`;

    // Factor: Police Stations
    document.getElementById('valPolice').innerText = route.police.val;
    document.getElementById('subPolice').innerText = route.police.sub;
    const barPolice = document.getElementById('barPolice');
    barPolice.style.width = `${route.police.percent}%`;
    barPolice.className = `meter-fill fill-${route.police.status}`;

    // ML Prediction Panel
    const mlPanel = document.getElementById('mlPredictionPanel');
    if (mlPanel && route.ml_risk && route.ml_risk.risk_label !== 'UNKNOWN') {
      const ml = route.ml_risk;
      const topReasons = (ml.explanation && ml.explanation.reasons) ? ml.explanation.reasons.slice(0, 3) : [];
      const reasonsHtml = topReasons.map(r => `<li style="margin-bottom:3px; font-size:11px; color:#9CA3AF;">${r}</li>`).join('');
      mlPanel.style.display = 'block';
      mlPanel.innerHTML = `
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:18px;">${ml.icon}</span>
            <div>
              <div style="font-size:11px; font-weight:700; letter-spacing:0.04em; color:#9CA3AF; text-transform:uppercase;">ML Risk Prediction</div>
              <div style="font-size:15px; font-weight:800; color:${ml.color}; letter-spacing:0.02em;">${ml.risk_label} RISK</div>
            </div>
          </div>
          <div style="text-align:right;">
            <div style="font-size:10px; color:#6B7280; margin-bottom:2px;">Confidence</div>
            <div style="font-size:14px; font-weight:700; color:${ml.color};">${ml.confidence_pct}%</div>
            <div style="width:60px; height:4px; background:#1F2937; border-radius:2px; margin-top:3px;">
              <div style="width:${ml.confidence_pct}%; height:100%; background:${ml.color}; border-radius:2px;"></div>
            </div>
          </div>
        </div>
        <div style="background:#111827; border-radius:6px; padding:8px 10px;">
          <div style="font-size:10px; font-weight:700; color:#6B7280; text-transform:uppercase; margin-bottom:4px;">Model Reasoning</div>
          <ul style="margin:0; padding-left:14px; list-style-type:disc;">${reasonsHtml}</ul>
        </div>
        <div style="font-size:10px; color:#6B7280; margin-top:6px; font-style:italic;">
          🤖 Model: ${ml.model_type || 'RandomForest'} · Trained on 300 labelled segments
        </div>
      `;
    } else if (mlPanel) {
      mlPanel.style.display = 'none';
    }
  }


  // Start Live Route Simulation HUD
  startNavigation() {
    this.isNavigating = true;
    this.simulationStep = 0;

    const route = ROUTES[this.selectedRouteIndex];

    // Hide search card & minimize sheet
    document.getElementById('tripSearchCard').style.transform = 'translateY(-100px)';
    document.getElementById('tripSearchCard').style.opacity = '0';
    document.getElementById('safetySheet').style.transform = 'translateY(120%)';

    // Show HUD
    const hud = document.getElementById('navHud');
    hud.classList.remove('hidden');

    document.getElementById('hudEta').innerText = route.time;
    document.getElementById('hudDist').innerText = route.distance;
    document.getElementById('hudScore').innerText = `${route.score}/100`;

    this.updateHudTurnInstruction();

    // Create moving tracker avatar
    const firstCoord = route.coordinates[0];
    if (this.navSimulationMarker) {
      this.map.removeLayer(this.navSimulationMarker);
    }

    const navIconHtml = `
      <div style="width: 32px; height: 32px; background: #10B981; border: 3px solid #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 15px #10B981;">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="white">
          <polygon points="3 11 22 2 13 21 11 13 3 11"/>
        </svg>
      </div>
    `;
    const navIcon = L.divIcon({
      html: navIconHtml,
      className: 'nav-sim-icon',
      iconSize: [32, 32],
      iconAnchor: [16, 16]
    });
    this.navSimulationMarker = L.marker(firstCoord, { icon: navIcon }).addTo(this.map);
    this.map.setView(firstCoord, 16, { animate: true });

    this.showToast('🧭 Live Safe Route Navigation Started');
  }

  // Advance step in navigation with dynamic remaining distance & ETA
  advanceNavStep() {
    const route = ROUTES[this.selectedRouteIndex];
    if (this.simulationStep < route.coordinates.length - 1) {
      this.simulationStep++;
      const nextCoord = route.coordinates[this.simulationStep];
      this.navSimulationMarker.setLatLng(nextCoord);
      this.map.panTo(nextCoord, { animate: true });
      this.updateHudTurnInstruction();
      this._updateHudProgress(route);

      if (this.simulationStep === route.coordinates.length - 1) {
        document.getElementById('hudEta').innerText = '0 min';
        document.getElementById('hudDist').innerText = '0.0 km';
        this.showToast('🎉 You have arrived safely at your destination!');
      }
    } else {
      this.showToast('You have reached the end of this route');
    }
  }

  // Compute remaining distance from current step to destination
  _updateHudProgress(route) {
    const coords = route.coordinates;
    let remainingM = 0;
    for (let i = this.simulationStep; i < coords.length - 1; i++) {
      const a = coords[i];
      const b = coords[i + 1];
      const dLat = (b[0] - a[0]) * Math.PI / 180;
      const dLng = (b[1] - a[1]) * Math.PI / 180;
      const sinLat = Math.sin(dLat / 2);
      const sinLng = Math.sin(dLng / 2);
      const c = sinLat * sinLat + Math.cos(a[0] * Math.PI / 180) * Math.cos(b[0] * Math.PI / 180) * sinLng * sinLng;
      remainingM += 6371000 * 2 * Math.atan2(Math.sqrt(c), Math.sqrt(1 - c));
    }
    const remainingKm = (remainingM / 1000).toFixed(1);
    const etaMin = Math.max(1, Math.round(remainingM / 75));  // 4.5 km/h walking
    document.getElementById('hudDist').innerText = `${remainingKm} km`;
    document.getElementById('hudEta').innerText = `${etaMin} min`;
  }

  updateHudTurnInstruction() {
    const route = ROUTES[this.selectedRouteIndex];
    const turn = route.turns[Math.min(this.simulationStep, route.turns.length - 1)];
    if (turn) {
      document.getElementById('hudNextAction').innerText = turn.action;
      document.getElementById('hudSafetyStatus').innerText = turn.safety;
    }
  }

  exitNavigation() {
    this.isNavigating = false;
    document.getElementById('navHud').classList.add('hidden');
    document.getElementById('tripSearchCard').style.transform = 'translateY(0)';
    document.getElementById('tripSearchCard').style.opacity = '1';
    document.getElementById('safetySheet').style.transform = 'translateY(0)';

    if (this.navSimulationMarker) {
      this.map.removeLayer(this.navSimulationMarker);
      this.navSimulationMarker = null;
    }

    // Reset map view to route bounds
    const coords = ROUTES[this.selectedRouteIndex].coordinates;
    this.map.fitBounds(L.latLngBounds(coords), { padding: [80, 80] });
    this.showToast('Navigation Ended');
  }

  // Emergency SOS Modal and Countdown System
  openSosModal() {
    const modal = document.getElementById('sosModal');
    if (this.gpsWatchId !== null) {
      navigator.geolocation.clearWatch(this.gpsWatchId);
      this.gpsWatchId = null;
    }

    // Reset current GPS state
    this.currentGps = {
      latitude: null,
      longitude: null,
      accuracy: null,
      timestamp: null
    };

    this.updateSosGpsDisplay({
      status: 'Acquiring Current GPS...',
      coords: 'Lat: Requesting... • Long: Requesting...',
      address: 'Current GPS position will be acquired after countdown',
      accuracy: null,
      isError: false
    });

    const contactStatusEl = document.getElementById('contactsAlertStatus');
    if (contactStatusEl) {
      contactStatusEl.innerText = 'Notify Contacts';
      contactStatusEl.style.color = '';
    }

    // Reset emergency mode displays
    const policeNameEl = document.getElementById('sosNearestPoliceName');
    const policeDistEl = document.getElementById('sosNearestPoliceDist');
    const notifStatusEl = document.getElementById('sosNotifStatusText');
    if (policeNameEl) policeNameEl.innerText = 'Locating nearest police post...';
    if (policeDistEl) policeDistEl.innerText = 'Distance: Calculating...';
    if (notifStatusEl) {
      notifStatusEl.innerText = 'Notification service not configured.';
      notifStatusEl.style.color = '#F59E0B';
    }

    // Render emergency contacts preview and primary contact button
    this.updateEmergencyContactsPreviewInSos();

    // If contacts haven't been fetched yet, fetch them in background
    if (!this.emergencyContacts || this.emergencyContacts.length === 0) {
      this.fetchEmergencyContacts().then(() => {
        this.updateEmergencyContactsPreviewInSos();
      }).catch(() => {});
    }

    modal.showModal();

    // Start 3 second countdown
    this.sosSecondsLeft = 3;
    const valEl = document.getElementById('sosCountdownVal');
    const card = document.getElementById('sosCountdownCard');
    const controls = document.getElementById('sosActiveControls');

    valEl.innerText = this.sosSecondsLeft;
    card.style.display = 'block';
    controls.style.display = 'none';

    clearInterval(this.sosCountdownInterval);
    this.sosCountdownInterval = setInterval(() => {
      this.sosSecondsLeft--;
      if (this.sosSecondsLeft > 0) {
        valEl.innerText = this.sosSecondsLeft;
      } else {
        clearInterval(this.sosCountdownInterval);
        card.style.display = 'none';
        controls.style.display = 'block';
        this.triggerSosAlarm();
      }
    }, 1000);
  }

  cancelSosCountdown() {
    clearInterval(this.sosCountdownInterval);
    if (this.gpsWatchId !== null) {
      navigator.geolocation.clearWatch(this.gpsWatchId);
      this.gpsWatchId = null;
    }
    this.stopSiren();
    if (this.sosEmergencyMarker && this.map) {
      try {
        this.map.removeLayer(this.sosEmergencyMarker);
        this.sosEmergencyMarker = null;
      } catch (e) {
        console.warn('Error removing SOS marker:', e);
      }
    }
    this.closeSosModal();
    this.showToast('Emergency alert cancelled');
  }

  cancelActiveSos() {
    clearInterval(this.sosCountdownInterval);
    if (this.gpsWatchId !== null) {
      navigator.geolocation.clearWatch(this.gpsWatchId);
      this.gpsWatchId = null;
      console.log('GPS watchPosition tracking stopped.');
    }
    this.stopSiren();
    if (this.sosEmergencyMarker && this.map) {
      try {
        this.map.removeLayer(this.sosEmergencyMarker);
        this.sosEmergencyMarker = null;
      } catch (e) {
        console.warn('Error removing SOS marker:', e);
      }
    }
    if (this.activeSosId) {
      const sosIdToCancel = this.activeSosId;
      this.activeSosId = null;
      apiRequest(`/api/sos/${sosIdToCancel}/cancel`, { method: 'POST', timeout: 5000 }).catch(err => {
        console.warn('Backend SOS cancellation notification failed:', err);
      });
    }
    this.closeSosModal();
    this.showToast('🚨 Emergency SOS cancelled. GPS tracking stopped.');
  }

  closeSosModal() {
    clearInterval(this.sosCountdownInterval);
    if (this.gpsWatchId !== null) {
      navigator.geolocation.clearWatch(this.gpsWatchId);
      this.gpsWatchId = null;
    }
    this.stopSiren();
    if (this.sosEmergencyMarker && this.map) {
      try {
        this.map.removeLayer(this.sosEmergencyMarker);
        this.sosEmergencyMarker = null;
      } catch (e) {
        console.warn('Error removing SOS marker:', e);
      }
    }
    const modal = document.getElementById('sosModal');
    if (modal && modal.open) {
      modal.close();
    }
  }

  updateEmergencyContactsPreviewInSos() {
    const listEl = document.getElementById('sosContactsChipsList');
    const primaryBtn = document.getElementById('dialPrimaryContactBtn');
    const primaryLabel = document.getElementById('primaryContactBtnLabel');
    const primarySub = document.getElementById('primaryContactBtnSub');

    const contacts = this.emergencyContacts || [];
    const enabledContacts = contacts.filter(c => c.enabled !== 0 && c.enabled !== false);
    const primaryContact = contacts.find(c => (c.is_primary === 1 || c.is_primary === true) && c.enabled !== 0 && c.enabled !== false) ||
                           contacts.find(c => c.is_primary === 1 || c.is_primary === true) ||
                           enabledContacts[0];

    // Update Primary Contact Dial Button
    if (primaryBtn) {
      if (primaryContact && primaryContact.phone) {
        primaryBtn.href = `tel:${primaryContact.phone}`;
        primaryBtn.classList.remove('hidden');
        if (primaryLabel) {
          primaryLabel.innerText = `CALL ${primaryContact.name.toUpperCase()}`;
        }
        if (primarySub) {
          primarySub.innerText = `${primaryContact.phone} • ${primaryContact.relationship || 'Primary Contact'}`;
        }
      } else {
        primaryBtn.classList.add('hidden');
      }
    }

    // Update Contacts Chips
    if (listEl) {
      if (enabledContacts.length === 0) {
        listEl.innerHTML = '<span class="contacts-loading-hint">No emergency contacts configured</span>';
      } else {
        listEl.innerHTML = enabledContacts.map(c => `
          <span class="sos-contact-chip ${c.is_primary ? 'is-primary' : ''}">
            ${c.is_primary ? '⭐ ' : ''}${this.escapeHtml(c.name)} (${this.escapeHtml(c.relationship || 'Contact')})
          </span>
        `).join('');
      }
    }
  }

  triggerSosAlarm() {
    // Start siren automatically on full trigger if sound enabled
    if (this.soundAlertsEnabled) {
      this.startSiren();
    }

    // Request actual current GPS location
    this.requestCurrentGpsAndDispatch('PANIC_BUTTON', 'Emergency SOS countdown completed & high-decibel siren triggered.');
  }

  // Request Actual Real Current GPS via navigator.geolocation.getCurrentPosition
  requestCurrentGpsAndDispatch(emergencyType = 'PANIC_BUTTON', notes = '') {
    if (!('geolocation' in navigator)) {
      this.updateSosGpsDisplay({
        status: 'GPS Not Supported',
        coords: 'Location unavailable',
        address: 'Geolocation is not supported by your browser.',
        isError: true
      });
      this.showToast('Location information is unavailable. Please check your device GPS.');
      return;
    }

    this.updateSosGpsDisplay({
      status: 'Acquiring Current GPS...',
      coords: 'Requesting satellite coordinates...',
      address: 'Detecting device location via browser geolocation...',
      isError: false
    });

    const geoOptions = {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0
    };

    navigator.geolocation.getCurrentPosition(
      (position) => {
        this.handleGpsSuccess(position, emergencyType, notes);
      },
      (error) => {
        this.handleGpsError(error);
      },
      geoOptions
    );
  }

  handleGpsSuccess(position, emergencyType = 'PANIC_BUTTON', notes = '') {
    const lat = position.coords.latitude;
    const lng = position.coords.longitude;
    const accuracy = position.coords.accuracy;
    const timestamp = position.timestamp || Date.now();

    // Verify valid coordinates exist
    if (
      typeof lat !== 'number' || typeof lng !== 'number' ||
      isNaN(lat) || isNaN(lng) ||
      lat < -90 || lat > 90 ||
      lng < -180 || lng > 180
    ) {
      this.showToast('Invalid GPS coordinates received from device.');
      this.updateSosGpsDisplay({
        status: 'Invalid GPS',
        coords: 'Corrupted GPS Coordinates',
        address: 'Device returned invalid latitude or longitude.',
        isError: true
      });
      return;
    }

    // Update real current GPS state
    this.currentGps = {
      latitude: lat,
      longitude: lng,
      accuracy: accuracy,
      timestamp: timestamp
    };

    // Update UI in SOS modal
    this.updateSosGpsDisplay({
      status: `Live GPS Active (±${Math.round(accuracy)}m)`,
      coords: `Lat: ${lat.toFixed(5)}° N • Long: ${lng.toFixed(5)}° E`,
      address: `Live GPS Fix • Accuracy: ±${Math.round(accuracy)}m (${new Date(timestamp).toLocaleTimeString()})`,
      isError: false
    });

    this.showToast('🚨 SOS ALERT TRIGGERED: Live GPS shared with emergency network');

    // Pan map to current GPS and display emergency marker
    this.showSosOnMap(lat, lng, accuracy);

    // Send payload to backend
    this.dispatchSosPayload(this.currentGps, emergencyType, notes);

    // Start watchPosition for active emergency mode
    this.startActiveGpsWatch();
  }

  handleGpsError(error) {
    let errorMsg = 'Unable to get your current location. Please try again.';
    let statusText = 'GPS Error';

    if (error.code === error.PERMISSION_DENIED) {
      errorMsg = 'Location permission is required to share your current location.';
      statusText = 'Permission Denied';
    } else if (error.code === error.TIMEOUT) {
      errorMsg = 'Unable to get your current location. Please try again.';
      statusText = 'GPS Request Timed Out';
    } else if (error.code === error.POSITION_UNAVAILABLE) {
      errorMsg = 'Location information is unavailable. Please check your device GPS.';
      statusText = 'Location Unavailable';
    }

    this.currentGps = {
      latitude: null,
      longitude: null,
      accuracy: null,
      timestamp: null
    };

    this.updateSosGpsDisplay({
      status: statusText,
      coords: 'GPS Coordinates Unavailable',
      address: errorMsg,
      isError: true
    });

    this.showToast(errorMsg);
    // DO NOT send fake coordinates!
  }

  startActiveGpsWatch() {
    if (!('geolocation' in navigator)) return;

    if (this.gpsWatchId !== null) {
      navigator.geolocation.clearWatch(this.gpsWatchId);
    }

    this.gpsWatchId = navigator.geolocation.watchPosition(
      (watchPos) => {
        const lat = watchPos.coords.latitude;
        const lng = watchPos.coords.longitude;
        const accuracy = watchPos.coords.accuracy;
        const timestamp = watchPos.timestamp || Date.now();

        if (
          typeof lat === 'number' && typeof lng === 'number' &&
          !isNaN(lat) && !isNaN(lng) &&
          lat >= -90 && lat <= 90 &&
          lng >= -180 && lng <= 180
        ) {
          this.currentGps = {
            latitude: lat,
            longitude: lng,
            accuracy: accuracy,
            timestamp: timestamp
          };

          this.updateSosGpsDisplay({
            status: `Live Tracking Active (±${Math.round(accuracy)}m)`,
            coords: `Lat: ${lat.toFixed(5)}° N • Long: ${lng.toFixed(5)}° E`,
            address: `Live Tracking Fix • Updated at ${new Date(timestamp).toLocaleTimeString()}`,
            accuracy: accuracy,
            isError: false
          });

          this.showSosOnMap(lat, lng, accuracy);
        }
      },
      (watchErr) => {
        console.warn('GPS watchPosition tracking warning:', watchErr);
      },
      {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 5000
      }
    );
  }

  updateSosGpsDisplay({ status, coords, address, accuracy = null, isError = false }) {
    const statusEl = document.getElementById('sosGpsStatusText');
    const coordsEl = document.getElementById('sosGeoCoords');
    const addressEl = document.getElementById('sosGeoAddress');
    const pulseEl = document.getElementById('sosGpsPulse');
    const accuracyPill = document.getElementById('sosGpsAccuracyPill');

    if (statusEl) statusEl.innerText = status;
    if (coordsEl) coordsEl.innerText = coords;
    if (addressEl) addressEl.innerText = address;

    if (accuracyPill) {
      if (accuracy != null && !isNaN(accuracy)) {
        accuracyPill.innerText = `GPS Accuracy: ±${Math.round(accuracy)}m`;
        accuracyPill.style.color = 'var(--safe-green-light)';
      } else if (isError) {
        accuracyPill.innerText = 'GPS Accuracy: Unavailable';
        accuracyPill.style.color = '#EF4444';
      } else {
        accuracyPill.innerText = 'GPS Accuracy: Detecting...';
        accuracyPill.style.color = 'var(--text-secondary)';
      }
    }

    if (pulseEl) {
      if (isError) {
        pulseEl.style.background = '#EF4444';
        pulseEl.style.boxShadow = '0 0 8px #EF4444';
      } else {
        pulseEl.style.background = '#10B981';
        pulseEl.style.boxShadow = '0 0 8px #10B981';
      }
    }
  }

  showSosOnMap(lat, lng, accuracy) {
    if (!this.map) return;
    try {
      if (this.sosEmergencyMarker) {
        this.sosEmergencyMarker.setLatLng([lat, lng]);
      } else {
        const sosIcon = L.divIcon({
          className: 'emergency-location-marker',
          html: `<div style="
            width: 22px; height: 22px;
            border-radius: 50%;
            background: #EF4444;
            border: 3px solid #FFFFFF;
            box-shadow: 0 0 16px #EF4444, 0 0 32px #EF4444;
          "></div>`,
          iconSize: [22, 22],
          iconAnchor: [11, 11]
        });
        this.sosEmergencyMarker = L.marker([lat, lng], { icon: sosIcon, zIndexOffset: 1500 }).addTo(this.map);
        this.sosEmergencyMarker.bindPopup(`<strong>🚨 Live SOS Position</strong><br>Accuracy: ±${Math.round(accuracy)}m`);
      }
      this.map.panTo([lat, lng]);
    } catch (e) {
      console.warn('Map update on SOS GPS warning:', e);
    }
  }

  // Send SOS Alert to Flask Backend API
  async dispatchSosPayload(gpsData, emergencyType = 'PANIC_BUTTON', notes = '') {
    // Before sending SOS verify that valid GPS coordinates exist.
    if (
      !gpsData ||
      gpsData.latitude == null ||
      gpsData.longitude == null ||
      isNaN(gpsData.latitude) ||
      isNaN(gpsData.longitude)
    ) {
      console.warn('Blocked SOS dispatch: Missing valid real GPS coordinates.');
      this.handleSosDispatchFailure('Emergency alert could not be processed. Please call 112 directly.');
      return;
    }

    const payload = {
      latitude: gpsData.latitude,
      longitude: gpsData.longitude,
      accuracy: gpsData.accuracy,
      location_name: `Current Location (${gpsData.latitude.toFixed(4)}°, ${gpsData.longitude.toFixed(4)}°)`,
      emergency_type: emergencyType,
      notes: notes || 'Emergency SOS broadcast with verified real-time GPS.'
    };

    try {
      const data = await apiRequest('/api/sos', {
        method: 'POST',
        body: JSON.stringify(payload),
        timeout: 9000
      });

      if (data && data.status === 'success') {
        this.activeSosId = data.sos_id;
        // Clear any previous SOS failure banner
        const failureBanner = document.getElementById('sosFailureBanner');
        if (failureBanner) failureBanner.classList.add('hidden');

        const station = data.nearest_police_dispatch?.station?.name || 'Local Police Post';
        const distKm = data.nearest_police_dispatch?.distance_km;
        const distMeters = data.nearest_police_dispatch?.distance_meters;

        const policeNameEl = document.getElementById('sosNearestPoliceName');
        const policeDistEl = document.getElementById('sosNearestPoliceDist');
        if (policeNameEl) policeNameEl.innerText = station;
        if (policeDistEl) {
          if (distKm != null) {
            policeDistEl.innerText = `Distance: ${distKm.toFixed(2)} km (${distMeters || Math.round(distKm * 1000)}m away)`;
          } else if (distMeters != null) {
            policeDistEl.innerText = `Distance: ${distMeters}m away`;
          } else {
            policeDistEl.innerText = 'Distance: Nearby patrol unit alerted';
          }
        }

        const distStr = distMeters ? ` (${distMeters}m away)` : '';
        this.showToast(`🚨 SOS Incident #${data.sos_id} Dispatched! ${station}${distStr}`);

        // Handle real backend emergency contact notification results
        this.handleNotificationResponse(data.notifications);
      } else {
        // SOS API returned error status
        this.handleSosDispatchFailure('Emergency alert could not be processed. Please call 112 directly.');
      }
    } catch (err) {
      console.error('SafeHer SOS API failed:', err);
      // SOS API failed due to network, timeout, or server error (500, 503, etc.)
      this.handleSosDispatchFailure('Emergency alert could not be processed. Please call 112 directly.');
    }
  }

  // Handle SOS dispatch failure: Keep dial button available and alert user immediately
  handleSosDispatchFailure(errorMessage) {
    const fallbackMsg = 'Emergency alert could not be processed. Please call 112 directly.';
    const displayMsg = errorMessage || fallbackMsg;

    // 1. Show toast message
    this.showToast(`⚠️ ${displayMsg}`, 7000);

    // 2. Keep emergency call button available and prominent
    const dialPoliceBtn = document.getElementById('dialPoliceBtn');
    if (dialPoliceBtn) {
      dialPoliceBtn.classList.remove('hidden');
      dialPoliceBtn.style.display = 'flex';
      dialPoliceBtn.classList.add('urgent-pulse');
      dialPoliceBtn.focus();
    }

    // 3. Update alert status in SOS modal
    const statusSpan = document.getElementById('contactsAlertStatus');
    if (statusSpan) {
      statusSpan.innerText = 'SOS Failed — Call 112';
      statusSpan.style.color = '#EF4444';
    }

    // 4. Render SOS failure banner above dial grid
    let failureBanner = document.getElementById('sosFailureBanner');
    if (!failureBanner) {
      const dialsGrid = document.querySelector('.sos-dials-grid');
      if (dialsGrid && dialsGrid.parentElement) {
        failureBanner = document.createElement('div');
        failureBanner.id = 'sosFailureBanner';
        failureBanner.className = 'sos-failure-banner';
        dialsGrid.parentElement.insertBefore(failureBanner, dialsGrid);
      }
    }
    if (failureBanner) {
      failureBanner.innerHTML = `
        <div class="sos-error-icon">⚠️</div>
        <div class="sos-error-text">
          <strong>Emergency Dispatch Failed</strong>
          <p>${this.escapeHtml(displayMsg)}</p>
        </div>
      `;
      failureBanner.classList.remove('hidden');
    }
  }

  // Handle actual backend SMS notification responses (never fakes SMS delivery)
  handleNotificationResponse(notifications) {
    const statusSpan = document.getElementById('contactsAlertStatus');
    const notifStatusEl = document.getElementById('sosNotifStatusText');

    if (!notifications) {
      const msg = 'Notification service not configured.';
      if (statusSpan) {
        statusSpan.innerText = msg;
        statusSpan.style.color = '#F59E0B';
      }
      if (notifStatusEl) {
        notifStatusEl.innerText = msg;
        notifStatusEl.style.color = '#F59E0B';
      }
      this.showToast(msg);
      return;
    }

    const { status, attempted = 0, successful = 0 } = notifications;

    if (status === 'sent') {
      const msg = `✓ Emergency alert sent to ${successful} emergency contact${successful === 1 ? '' : 's'}.`;
      if (statusSpan) {
        statusSpan.innerText = msg;
        statusSpan.style.color = '#34D399';
      }
      if (notifStatusEl) {
        notifStatusEl.innerText = msg;
        notifStatusEl.style.color = '#34D399';
      }
      this.showToast(msg);
    } else if (status === 'partial') {
      const msg = `⚠️ Emergency alert sent to ${successful} of ${attempted} contacts.`;
      if (statusSpan) {
        statusSpan.innerText = msg;
        statusSpan.style.color = '#F59E0B';
      }
      if (notifStatusEl) {
        notifStatusEl.innerText = msg;
        notifStatusEl.style.color = '#F59E0B';
      }
      this.showToast(msg);
    } else if (status === 'failed') {
      const msg = '❌ Emergency alert could not be sent to emergency contacts.';
      if (statusSpan) {
        statusSpan.innerText = msg;
        statusSpan.style.color = '#EF4444';
      }
      if (notifStatusEl) {
        notifStatusEl.innerText = msg;
        notifStatusEl.style.color = '#EF4444';
      }
      this.showToast(msg);
    } else if (status === 'not_configured') {
      const msg = 'Notification service not configured.';
      if (statusSpan) {
        statusSpan.innerText = msg;
        statusSpan.style.color = '#F59E0B';
      }
      if (notifStatusEl) {
        notifStatusEl.innerText = msg;
        notifStatusEl.style.color = '#F59E0B';
      }
      this.showToast(msg);
    } else if (status === 'no_contacts') {
      const msg = '⚠️ No enabled emergency contacts to notify.';
      if (statusSpan) {
        statusSpan.innerText = msg;
        statusSpan.style.color = '#94A3B8';
      }
      if (notifStatusEl) {
        notifStatusEl.innerText = msg;
        notifStatusEl.style.color = '#94A3B8';
      }
      this.showToast('Emergency alert recorded, but no enabled emergency contacts were found.');
    } else {
      const msg = 'Notification service not configured.';
      if (statusSpan) {
        statusSpan.innerText = msg;
        statusSpan.style.color = '#F59E0B';
      }
      if (notifStatusEl) {
        notifStatusEl.innerText = msg;
        notifStatusEl.style.color = '#F59E0B';
      }
      this.showToast(msg);
    }
  }

  // Backward compatibility alias for any caller
  dispatchSosAlert(emergencyType = 'PANIC_BUTTON', notes = '') {
    if (this.currentGps && this.currentGps.latitude != null && this.currentGps.longitude != null) {
      this.dispatchSosPayload(this.currentGps, emergencyType, notes);
    } else {
      this.requestCurrentGpsAndDispatch(emergencyType, notes);
    }
  }

  // High-Decibel Siren using Web Audio API Oscillator
  toggleSiren() {
    if (this.isSirenPlaying) {
      this.stopSiren();
    } else {
      this.startSiren();
    }
  }

  startSiren() {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!this.audioCtx) {
        this.audioCtx = new AudioCtx();
      }
      if (this.audioCtx.state === 'suspended') {
        this.audioCtx.resume();
      }

      this.isSirenPlaying = true;
      const sirenBtn = document.getElementById('toggleSirenBtn');
      const sirenBtnText = document.getElementById('sirenBtnText');
      if (sirenBtn) sirenBtn.classList.add('siren-active');
      if (sirenBtnText) sirenBtnText.innerText = 'Stop Siren';

      // Create alternating frequency oscillator
      this.sirenOsc = this.audioCtx.createOscillator();
      const gainNode = this.audioCtx.createGain();
      gainNode.gain.setValueAtTime(0.3, this.audioCtx.currentTime);

      this.sirenOsc.type = 'sawtooth';
      this.sirenOsc.connect(gainNode);
      gainNode.connect(this.audioCtx.destination);

      let highFreq = false;
      this.sirenOsc.frequency.setValueAtTime(700, this.audioCtx.currentTime);
      this.sirenOsc.start();

      this.sirenInterval = setInterval(() => {
        if (!this.sirenOsc) return;
        highFreq = !highFreq;
        const targetFreq = highFreq ? 960 : 700;
        this.sirenOsc.frequency.linearRampToValueAtTime(targetFreq, this.audioCtx.currentTime + 0.35);
      }, 400);

    } catch (e) {
      console.warn('Web Audio playback error or blocked:', e);
    }
  }

  stopSiren() {
    this.isSirenPlaying = false;
    clearInterval(this.sirenInterval);
    if (this.sirenOsc) {
      try {
        this.sirenOsc.stop();
        this.sirenOsc.disconnect();
      } catch (_) {}
      this.sirenOsc = null;
    }
    const sirenBtn = document.getElementById('toggleSirenBtn');
    const sirenBtnText = document.getElementById('sirenBtnText');
    if (sirenBtn) sirenBtn.classList.remove('siren-active');
    if (sirenBtnText) sirenBtnText.innerText = 'Sound Siren';
  }

  // Toast Notification helper
  showToast(msg) {
    const toast = document.getElementById('toastNotification');
    const toastMsg = document.getElementById('toastMsg');
    toastMsg.innerText = msg;
    toast.classList.remove('hidden');

    setTimeout(() => {
      toast.classList.add('hidden');
    }, 3500);
  }

  // Automated GPS Current Location Detection
  useCurrentLocation() {
    if (!('geolocation' in navigator)) {
      this.showToast('⚠️ Geolocation is not supported by your browser');
      return;
    }

    const btn = document.getElementById('autoLocateBtn');
    const btnText = document.getElementById('autoLocateText');
    if (btn) btn.classList.add('locating');
    if (btnText) btnText.innerText = 'Locating...';

    this.showToast('📡 Detecting your current GPS location...');

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        if (btn) btn.classList.remove('locating');
        if (btnText) btnText.innerText = 'GPS Auto-Detect';

        const lat = position.coords.latitude;
        const lng = position.coords.longitude;
        this.startCoords = [lat, lng];

        // Reverse geocode via OpenStreetMap Nominatim or fallback coordinates
        let locationName = `Current Location (${lat.toFixed(4)}, ${lng.toFixed(4)})`;
        try {
          const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`, {
            headers: { 'Accept-Language': 'en' }
          });
          if (res.ok) {
            const data = await res.json();
            if (data && data.address) {
              const addr = data.address;
              const primary = addr.amenity || addr.road || addr.suburb || addr.neighbourhood || addr.quarter || '';
              const city = addr.city || addr.town || addr.county || '';
              if (primary) {
                locationName = city ? `${primary}, ${city}` : primary;
              } else if (data.display_name) {
                locationName = data.display_name.split(',').slice(0, 2).join(',');
              }
            }
          }
        } catch (e) {
          console.warn('Reverse geocoding network error, using GPS coordinates:', e);
        }

        this.startLocation = locationName;
        const startInput = document.getElementById('startLocationInput');
        if (startInput) startInput.value = locationName;

        // Update user map marker and recenter
        if (this.userMarker) {
          this.userMarker.setLatLng(this.startCoords);
          this.userMarker.setPopupContent(`<b>Your Current Location (GPS)</b><br>${this.escapeHtml(locationName)}`);
        }
        this.map.setView(this.startCoords, 15, { animate: true });

        this.showToast(`📍 Found your location: ${locationName}`);

        // Recalculate safest routes from user's current GPS location
        this.fetchRoutes();
      },
      (error) => {
        if (btn) btn.classList.remove('locating');
        if (btnText) btnText.innerText = 'GPS Auto-Detect';

        let errorMsg = '⚠️ Unable to retrieve your GPS location.';
        if (error.code === error.PERMISSION_DENIED) {
          errorMsg = '⚠️ GPS permission denied. Please allow location access or type address.';
        } else if (error.code === error.TIMEOUT) {
          errorMsg = '⚠️ GPS location request timed out. Retrying or enter manually.';
        }
        this.showToast(errorMsg);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 30000
      }
    );
  }

  // Geocode location string via local database or OpenStreetMap
  async geocodeLocation(query) {
    if (!query || !query.trim()) return null;
    const q = query.trim().toLowerCase();

    // 1. Check local known safe locations list first
    const match = KNOWN_LOCATIONS.find(loc =>
      loc.name.toLowerCase().includes(q) || q.includes(loc.name.toLowerCase())
    );
    if (match) {
      return { name: match.name, coords: match.coords };
    }

    // 2. Query Nominatim OpenStreetMap Geocoding API
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`, {
        headers: { 'Accept-Language': 'en' }
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.length > 0) {
          const lat = parseFloat(data[0].lat);
          const lon = parseFloat(data[0].lon);
          const shortName = data[0].display_name.split(',').slice(0, 3).join(', ');
          return { name: shortName || query, coords: [lat, lon] };
        }
      }
    } catch (e) {
      console.warn('Geocoding request failed:', e);
    }
    return null;
  }

  // Apply user-typed location inputs and recalculate routes
  async applyLocationInputs() {
    const startInput = document.getElementById('startLocationInput');
    const destInput = document.getElementById('destLocationInput');
    if (!startInput || !destInput) return;

    const startVal = startInput.value.trim();
    const destVal = destInput.value.trim();

    if (!startVal || !destVal) {
      this.showToast('⚠️ Please enter both start and destination locations.');
      return;
    }

    this.showToast('🔍 Searching locations & calculating safest routes...');

    // Geocode start if text changed
    if (startVal !== this.startLocation) {
      const geoStart = await this.geocodeLocation(startVal);
      if (geoStart) {
        this.startCoords = geoStart.coords;
        this.startLocation = geoStart.name;
        startInput.value = geoStart.name;
      } else {
        this.startLocation = startVal;
      }
    }

    // Geocode destination if text changed
    if (destVal !== this.destLocation) {
      const geoDest = await this.geocodeLocation(destVal);
      if (geoDest) {
        this.destCoords = geoDest.coords;
        this.destLocation = geoDest.name;
        destInput.value = geoDest.name;
      } else {
        this.destLocation = destVal;
      }
    }

    // Update map markers
    if (this.userMarker) {
      this.userMarker.setLatLng(this.startCoords);
      this.userMarker.setPopupContent(`<b>Start Location</b><br>${this.escapeHtml(this.startLocation)}`);
    }
    if (this.destMarker) {
      this.destMarker.setLatLng(this.destCoords);
      this.destMarker.setPopupContent(`<b>Destination</b><br>${this.escapeHtml(this.destLocation)}`);
    }

    // Recalculate routes via Flask backend
    await this.fetchRoutes();
  }

  // Setup Location Suggestions Dropdown for instant selection & GPS prompt
  setupLocationSuggestions() {
    const dropdown = document.getElementById('locationSuggestions');
    const startInput = document.getElementById('startLocationInput');
    const destInput = document.getElementById('destLocationInput');
    if (!dropdown || !startInput || !destInput) return;

    let activeInput = null;

    const renderSuggestions = (inputEl) => {
      activeInput = inputEl;
      const q = inputEl.value.trim().toLowerCase();
      let html = `
        <div class="suggestion-item" data-action="gps">
          <span class="suggestion-icon">🎯</span>
          <div class="suggestion-text">
            <strong>Use My Current Location</strong>
            <span style="display:block; font-size:0.68rem; color:var(--text-muted);">Auto-detect via GPS</span>
          </div>
        </div>
      `;

      const matches = KNOWN_LOCATIONS.filter(loc => !q || loc.name.toLowerCase().includes(q));
      matches.slice(0, 5).forEach(loc => {
        html += `
          <div class="suggestion-item" data-name="${this.escapeHtml(loc.name)}" data-lat="${loc.coords[0]}" data-lng="${loc.coords[1]}">
            <span class="suggestion-icon">${loc.icon || '📍'}</span>
            <div class="suggestion-text">
              <strong>${this.escapeHtml(loc.name)}</strong>
              <span style="display:block; font-size:0.68rem; color:var(--text-muted);">${loc.type}</span>
            </div>
          </div>
        `;
      });

      dropdown.innerHTML = html;
      dropdown.classList.remove('hidden');
    };

    [startInput, destInput].forEach(inp => {
      inp.addEventListener('focus', () => renderSuggestions(inp));
      inp.addEventListener('input', () => renderSuggestions(inp));
    });

    dropdown.addEventListener('click', (e) => {
      const item = e.target.closest('.suggestion-item');
      if (!item || !activeInput) return;

      if (item.dataset.action === 'gps') {
        dropdown.classList.add('hidden');
        this.useCurrentLocation();
        return;
      }

      const name = item.dataset.name;
      const lat = parseFloat(item.dataset.lat);
      const lng = parseFloat(item.dataset.lng);

      if (activeInput === startInput) {
        this.startLocation = name;
        this.startCoords = [lat, lng];
        startInput.value = name;
        if (this.userMarker) {
          this.userMarker.setLatLng(this.startCoords);
          this.userMarker.setPopupContent(`<b>Start Location</b><br>${this.escapeHtml(name)}`);
        }
      } else {
        this.destLocation = name;
        this.destCoords = [lat, lng];
        destInput.value = name;
        if (this.destMarker) {
          this.destMarker.setLatLng(this.destCoords);
          this.destMarker.setPopupContent(`<b>Destination</b><br>${this.escapeHtml(name)}`);
        }
      }

      dropdown.classList.add('hidden');
      this.showToast(`Selected: ${name}`);
      this.fetchRoutes();
    });

    document.addEventListener('click', (e) => {
      if (!e.target.closest('.trip-search-card')) {
        dropdown.classList.add('hidden');
      }
    });
  }

  // Bind Event Listeners
  bindEvents() {
    // Start Safe Route Button
    document.getElementById('startSafeRouteBtn').addEventListener('click', () => {
      this.startNavigation();
    });

    // Advance simulation step
    document.getElementById('simulateStepBtn').addEventListener('click', () => {
      this.advanceNavStep();
    });

    // Exit Navigation
    document.getElementById('exitNavBtn').addEventListener('click', () => {
      this.exitNavigation();
    });

    // Quick SOS in Header and Floating SOS
    document.getElementById('quickSosTriggerBtn').addEventListener('click', () => {
      this.openSosModal();
    });
    document.getElementById('mainSosBtn').addEventListener('click', () => {
      this.openSosModal();
    });

    // SOS Modal close & cancel
    document.getElementById('closeSosBtn').addEventListener('click', () => {
      this.cancelActiveSos();
    });
    document.getElementById('cancelSosCountdownBtn').addEventListener('click', () => {
      this.cancelSosCountdown();
    });
    const cancelActiveSosBtn = document.getElementById('cancelActiveSosBtn');
    if (cancelActiveSosBtn) {
      cancelActiveSosBtn.addEventListener('click', () => {
        this.cancelActiveSos();
      });
    }

    // Siren button
    document.getElementById('toggleSirenBtn').addEventListener('click', () => {
      this.toggleSiren();
    });

    // Alert Emergency Contacts (SMS Notification Service)
    document.getElementById('alertFamilyBtn').addEventListener('click', () => {
      const statusSpan = document.getElementById('contactsAlertStatus');
      if (statusSpan) {
        statusSpan.innerText = 'Notifying contacts...';
        statusSpan.style.color = '#94A3B8';
      }
      this.dispatchSosAlert('EMERGENCY_CONTACT_ALERT', 'Manual SOS alert triggered for emergency contacts.');
    });

    // Share Trip Button
    document.getElementById('shareTripBtn').addEventListener('click', () => {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(window.location.href);
      }
      this.showToast('🔗 Live Trip Tracking Link copied to clipboard');
    });

    // Recenter / My Location Button (GPS)
    document.getElementById('recenterBtn').addEventListener('click', () => {
      this.useCurrentLocation();
    });

    // Toggle Safety Zones Button
    const toggleZonesBtn = document.getElementById('toggleSafetyZonesBtn');
    toggleZonesBtn.addEventListener('click', () => {
      this.showSafetyZones = !this.showSafetyZones;
      toggleZonesBtn.classList.toggle('active', this.showSafetyZones);
      this.drawSafetyZones();
      this.showToast(this.showSafetyZones ? 'Safety Zones displayed' : 'Safety Zones hidden');
    });

    // Toggle Police Button
    const togglePoliceBtn = document.getElementById('togglePoliceBtn');
    togglePoliceBtn.addEventListener('click', () => {
      this.showPolice = !this.showPolice;
      togglePoliceBtn.classList.toggle('active', this.showPolice);
      this.drawPoliceStations();
      this.showToast(this.showPolice ? 'Police booths displayed' : 'Police booths hidden');
    });

    // Sound toggle
    const soundToggleBtn = document.getElementById('soundToggleBtn');
    soundToggleBtn.addEventListener('click', () => {
      this.soundAlertsEnabled = !this.soundAlertsEnabled;
      soundToggleBtn.style.color = this.soundAlertsEnabled ? '#ffffff' : '#6B7280';
      this.showToast(this.soundAlertsEnabled ? 'Sound alerts enabled' : 'Sound alerts muted');
    });

    // Sheet Drag handle (toggle expand)
    const sheetHandle = document.getElementById('sheetHandle');
    const sheet = document.getElementById('safetySheet');
    sheetHandle.addEventListener('click', () => {
      sheet.classList.toggle('expanded');
    });

    // Swap Destination (Dynamic Backend Recalculation)
    document.getElementById('swapLocBtn').addEventListener('click', () => {
      const tempLoc = this.startLocation;
      this.startLocation = this.destLocation;
      this.destLocation = tempLoc;

      const tempCoords = this.startCoords;
      this.startCoords = this.destCoords;
      this.destCoords = tempCoords;

      const startInput = document.getElementById('startLocationInput');
      const destInput = document.getElementById('destLocationInput');
      if (startInput) startInput.value = this.startLocation;
      if (destInput) destInput.value = this.destLocation;

      if (this.userMarker) {
        this.userMarker.setLatLng(this.startCoords);
        this.userMarker.setPopupContent(`<b>Start Location</b><br>${this.escapeHtml(this.startLocation)}`);
      }
      if (this.destMarker) {
        this.destMarker.setLatLng(this.destCoords);
        this.destMarker.setPopupContent(`<b>Destination</b><br>${this.escapeHtml(this.destLocation)}`);
      }

      this.showToast('Route endpoints swapped — calculating safest paths...');
      this.fetchRoutes();
    });

    // GPS Auto-Detect Button in Search Header Card
    const autoLocateBtn = document.getElementById('autoLocateBtn');
    if (autoLocateBtn) {
      autoLocateBtn.addEventListener('click', () => {
        this.useCurrentLocation();
      });
    }

    // Apply Search Button
    const applySearchBtn = document.getElementById('applySearchBtn');
    if (applySearchBtn) {
      applySearchBtn.addEventListener('click', () => {
        this.applyLocationInputs();
      });
    }

    // Enter Key on Start and Destination Inputs
    const startInput = document.getElementById('startLocationInput');
    const destInput = document.getElementById('destLocationInput');
    if (startInput) {
      startInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          this.applyLocationInputs();
        }
      });
    }
    if (destInput) {
      destInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          this.applyLocationInputs();
        }
      });
    }

    // Clear buttons for inputs
    const clearStartBtn = document.getElementById('clearStartBtn');
    const clearDestBtn = document.getElementById('clearDestBtn');
    if (clearStartBtn && startInput) {
      startInput.addEventListener('input', () => {
        clearStartBtn.classList.toggle('hidden', !startInput.value);
      });
      clearStartBtn.addEventListener('click', () => {
        startInput.value = '';
        clearStartBtn.classList.add('hidden');
        startInput.focus();
      });
    }
    if (clearDestBtn && destInput) {
      destInput.addEventListener('input', () => {
        clearDestBtn.classList.toggle('hidden', !destInput.value);
      });
      clearDestBtn.addEventListener('click', () => {
        destInput.value = '';
        clearDestBtn.classList.add('hidden');
        destInput.focus();
      });
    }

    // AI Safety Assistant Chat Dialog Bindings
    const chatToggleBtn = document.getElementById('chatToggleBtn');
    const chatModal = document.getElementById('chatModal');
    const closeChatBtn = document.getElementById('closeChatBtn');

    if (chatToggleBtn && chatModal) {
      chatToggleBtn.addEventListener('click', () => {
        chatModal.showModal();
        const chatInput = document.getElementById('chatInput');
        if (chatInput) chatInput.focus();
      });
    }

    if (closeChatBtn && chatModal) {
      closeChatBtn.addEventListener('click', () => {
        chatModal.close();
      });
    }

    // Chat Form submission
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');

    if (chatForm && chatInput) {
      chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const msg = chatInput.value.trim();
        if (!msg) return;
        chatInput.value = '';
        this.sendChatMessage(msg);
      });
    }

    // Chat Quick Prompt Chips (Event Delegation)
    const quickPromptsContainer = document.getElementById('chatQuickPrompts');
    if (quickPromptsContainer) {
      quickPromptsContainer.addEventListener('click', (e) => {
        const chip = e.target.closest('.prompt-chip');
        if (chip) {
          const q = chip.getAttribute('data-query');
          if (q) {
            this.sendChatMessage(q);
          }
        }
      });
    }

    // Emergency Action in Chat (Delegation to open SOS modal)
    const chatMsgContainer = document.getElementById('chatMessages');
    if (chatMsgContainer) {
      chatMsgContainer.addEventListener('click', (e) => {
        const sosBtn = e.target.closest('.emergency-chat-sos-btn');
        if (sosBtn) {
          if (chatModal && chatModal.open) {
            chatModal.close();
          }
          this.openSosModal();
        }
      });
    }

    // Emergency Contacts Modal & Forms
    const contactsToggleBtn = document.getElementById('contactsToggleBtn');
    const closeContactsBtn = document.getElementById('closeContactsBtn');
    const openAddContactBtn = document.getElementById('openAddContactBtn');
    const cancelContactFormBtn = document.getElementById('cancelContactFormBtn');
    const cancelContactFormIconBtn = document.getElementById('cancelContactFormIconBtn');
    const contactForm = document.getElementById('contactForm');
    const cancelDeleteContactBtn = document.getElementById('cancelDeleteContactBtn');
    const confirmDeleteContactBtn = document.getElementById('confirmDeleteContactBtn');

    if (contactsToggleBtn) {
      contactsToggleBtn.addEventListener('click', () => {
        this.openContactsModal();
      });
    }

    if (closeContactsBtn) {
      closeContactsBtn.addEventListener('click', () => {
        this.closeContactsModal();
      });
    }

    if (openAddContactBtn) {
      openAddContactBtn.addEventListener('click', () => {
        this.showContactForm();
      });
    }

    if (cancelContactFormBtn) {
      cancelContactFormBtn.addEventListener('click', () => {
        this.hideContactForm();
      });
    }

    if (cancelContactFormIconBtn) {
      cancelContactFormIconBtn.addEventListener('click', () => {
        this.hideContactForm();
      });
    }

    if (contactForm) {
      contactForm.addEventListener('submit', (e) => {
        this.handleSaveContact(e);
      });
    }

    if (cancelDeleteContactBtn) {
      cancelDeleteContactBtn.addEventListener('click', () => {
        this.cancelDeleteContact();
      });
    }

    if (confirmDeleteContactBtn) {
      confirmDeleteContactBtn.addEventListener('click', () => {
        this.confirmDeleteContact();
      });
    }
  }

  // Format bot reply for safe, rich display
  formatBotReply(text) {
    if (!text) return '';
    let safe = this.escapeHtml(text);
    // Convert markdown bold **text** to <strong>text</strong>
    safe = safe.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Convert newlines to <br>
    safe = safe.replace(/\n/g, '<br>');
    return safe;
  }

  // Send AI Safety Assistant Chat Message
  sendChatMessage(text) {
    const container = document.getElementById('chatMessages');
    if (!container) return;

    // Append User Message
    const userMsgEl = document.createElement('div');
    userMsgEl.className = 'chat-msg user-msg';
    userMsgEl.innerHTML = `
      <div class="msg-bubble user-bubble">${this.escapeHtml(text)}</div>
      <span class="msg-time">Just now</span>
    `;
    container.appendChild(userMsgEl);

    // Typing Indicator
    const typingEl = document.createElement('div');
    typingEl.className = 'chat-msg bot-msg';
    typingEl.id = 'chatTypingIndicator';
    typingEl.innerHTML = `
      <div class="chat-bot-avatar-sm">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
      </div>
      <div class="chat-msg-body">
        <div class="msg-bubble bot-bubble">
          <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    `;
    container.appendChild(typingEl);
    container.scrollTop = container.scrollHeight;

    // Call Backend /api/chat with user coordinates using apiRequest
    apiRequest('/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        message: text,
        current_location: this.startCoords || [28.6328, 77.2155],
        time_of_day: 'auto'
      }),
      timeout: 8000
    })
      .then(data => {
        const ind = document.getElementById('chatTypingIndicator');
        if (ind) ind.remove();

        const botMsgEl = document.createElement('div');
        botMsgEl.className = 'chat-msg bot-msg';

        let recsHtml = '';
        if (data.recommendations && data.recommendations.length > 0) {
          const recItems = data.recommendations.map(r => `<div class="rec-item">✓ ${this.escapeHtml(r)}</div>`).join('');
          recsHtml = `
            <div class="chat-recommendations">
              <span class="recs-title">Safety Recommendations</span>
              ${recItems}
            </div>
          `;
        }

        let sosCardHtml = '';
        if (data.show_sos_button === true || data.intent === 'emergency') {
          sosCardHtml = `
            <div class="emergency-chat-card">
              <div class="emergency-chat-card-title">
                <span>🚨</span> Instant Emergency Protection
              </div>
              <button type="button" class="emergency-chat-sos-btn">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:4px;">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                </svg>
                <span>Trigger Emergency SOS (Broadcast &amp; Siren)</span>
              </button>
            </div>
          `;
          this.showToast('🚨 Emergency guidance provided — tap SOS if needed');
        }

        const formattedReply = this.formatBotReply(data.reply || 'Stay safe and stick to well-lit main corridors.');

        botMsgEl.innerHTML = `
          <div class="chat-bot-avatar-sm">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
          </div>
          <div class="chat-msg-body">
            <div class="msg-bubble bot-bubble">
              ${formattedReply}
            </div>
            ${recsHtml}
            ${sosCardHtml}
            <span class="msg-time">Just now</span>
          </div>
        `;
        container.appendChild(botMsgEl);
        container.scrollTop = container.scrollHeight;
      })
      .catch(err => {
        const ind = document.getElementById('chatTypingIndicator');
        if (ind) ind.remove();

        const botMsgEl = document.createElement('div');
        botMsgEl.className = 'chat-msg bot-msg';
        botMsgEl.innerHTML = `
          <div class="chat-bot-avatar-sm">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
          </div>
          <div class="chat-msg-body">
            <div class="msg-bubble bot-bubble">
              🛡️ <strong>Safety Advisory:</strong> For optimal night safety, prioritize the <strong>Main Boulevard Safe Corridor</strong> (Score 92/100). Keep to illuminated pedestrian ways and remember national emergency helplines: <strong>112</strong> (Police) and <strong>1091</strong> (Women Safety).
            </div>
            <span class="msg-time">Offline safety guide</span>
          </div>
        `;
        container.appendChild(botMsgEl);
        container.scrollTop = container.scrollHeight;
      });
  }

  // =========================================================================
  // Emergency Contacts System
  // =========================================================================

  openContactsModal() {
    const modal = document.getElementById('contactsModal');
    if (!modal) return;
    this.hideContactForm();
    this.cancelDeleteContact();
    if (typeof modal.showModal === 'function') {
      modal.showModal();
    } else {
      modal.setAttribute('open', '');
    }
    this.fetchEmergencyContacts();
  }

  closeContactsModal() {
    const modal = document.getElementById('contactsModal');
    if (modal) {
      if (typeof modal.close === 'function') {
        modal.close();
      } else {
        modal.removeAttribute('open');
      }
    }
    this.hideContactForm();
    this.cancelDeleteContact();
  }

  async fetchEmergencyContacts() {
    const errorBanner = document.getElementById('contactsErrorBanner');
    const errorText = document.getElementById('contactsErrorBannerText');
    const container = document.getElementById('contactsListContainer');

    if (errorBanner) errorBanner.classList.add('hidden');

    if (container && (!this.emergencyContacts || this.emergencyContacts.length === 0)) {
      container.innerHTML = `
        <div class="contacts-loading-state">
          <p>Loading emergency contacts...</p>
        </div>
      `;
    }

    try {
      const data = await apiRequest('/api/contacts', { timeout: 6000 });
      if (data && data.status === 'success') {
        this.emergencyContacts = data.contacts || [];
        this.renderContactsList();
      } else {
        throw new Error((data && data.message) || 'Unable to load emergency contacts.');
      }
    } catch (err) {
      console.warn('Emergency contacts fetch failed:', err);
      const displayMsg = 'Unable to load emergency contacts.';
      if (errorBanner && errorText) {
        errorText.innerText = displayMsg;
        errorBanner.classList.remove('hidden');
      }
      this.showToast(displayMsg);
      this.renderContactsList();
    }
  }

  renderContactsList() {
    const container = document.getElementById('contactsListContainer');
    const badge = document.getElementById('contactsCountBadge');
    if (!container) return;

    const count = this.emergencyContacts ? this.emergencyContacts.length : 0;
    if (badge) {
      badge.innerText = `${count} Contact${count === 1 ? '' : 's'}`;
    }

    if (count === 0) {
      container.innerHTML = `
        <div class="contacts-empty-state">
          <div class="empty-contacts-icon">👥</div>
          <p><strong>No emergency contacts configured</strong></p>
          <p>Add trusted family, friends, or guardians to receive alerts during an emergency.</p>
        </div>
      `;
      return;
    }

    let html = '';
    this.emergencyContacts.forEach(contact => {
      const isPrimary = !!contact.is_primary;
      const isEnabled = !!contact.enabled;

      html += `
        <div class="contact-card ${isPrimary ? 'is-primary' : ''} ${!isEnabled ? 'is-disabled' : ''}" data-id="${contact.id}">
          <div class="contact-card-header">
            <div class="contact-identity">
              <strong class="contact-name">${this.escapeHtml(contact.name)}</strong>
              <span class="contact-rel-badge">${this.escapeHtml(contact.relationship)}</span>
            </div>
            <div class="contact-badges-wrap">
              ${isPrimary ? '<span class="badge-primary">PRIMARY</span>' : ''}
              ${!isEnabled ? '<span class="badge-disabled">DISABLED</span>' : ''}
            </div>
          </div>
          <div class="contact-phone-row">
            <span class="contact-phone-text">${this.escapeHtml(contact.phone)}</span>
          </div>
          <div class="contact-card-actions">
            <a href="tel:${this.escapeHtml(contact.phone)}" class="call-contact-btn" title="Call ${this.escapeHtml(contact.name)}">📞 Call</a>
            <button type="button" class="edit-contact-btn" data-id="${contact.id}">Edit</button>
            <button type="button" class="delete-contact-btn" data-id="${contact.id}">Delete</button>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;

    // Attach card action listeners
    container.querySelectorAll('.edit-contact-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = parseInt(e.currentTarget.getAttribute('data-id'), 10);
        this.showContactForm(id);
      });
    });

    container.querySelectorAll('.delete-contact-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = parseInt(e.currentTarget.getAttribute('data-id'), 10);
        this.promptDeleteContact(id);
      });
    });
  }

  showContactForm(contactId = null) {
    const formCard = document.getElementById('contactFormContainer');
    const formTitle = document.getElementById('contactFormTitle');
    const idInput = document.getElementById('contactIdInput');
    const nameInput = document.getElementById('contactNameInput');
    const phoneInput = document.getElementById('contactPhoneInput');
    const relInput = document.getElementById('contactRelInput');
    const isPrimaryInput = document.getElementById('contactIsPrimaryInput');
    const enabledInput = document.getElementById('contactEnabledInput');
    const errorBox = document.getElementById('contactFormError');

    if (!formCard) return;

    if (errorBox) {
      errorBox.classList.add('hidden');
      errorBox.innerText = '';
    }

    if (contactId) {
      const contact = this.emergencyContacts.find(c => c.id === contactId);
      if (contact) {
        if (formTitle) formTitle.innerText = 'Edit Emergency Contact';
        if (idInput) idInput.value = contact.id;
        if (nameInput) nameInput.value = contact.name;
        if (phoneInput) phoneInput.value = contact.phone;
        if (relInput) relInput.value = contact.relationship;
        if (isPrimaryInput) isPrimaryInput.checked = !!contact.is_primary;
        if (enabledInput) enabledInput.checked = !!contact.enabled;
      }
    } else {
      if (formTitle) formTitle.innerText = 'Add Emergency Contact';
      if (idInput) idInput.value = '';
      if (nameInput) nameInput.value = '';
      if (phoneInput) phoneInput.value = '';
      if (relInput) relInput.value = '';
      if (isPrimaryInput) isPrimaryInput.checked = false;
      if (enabledInput) enabledInput.checked = true;
    }

    formCard.classList.remove('hidden');
    if (nameInput) nameInput.focus();
  }

  hideContactForm() {
    const formCard = document.getElementById('contactFormContainer');
    const errorBox = document.getElementById('contactFormError');
    if (formCard) formCard.classList.add('hidden');
    if (errorBox) {
      errorBox.classList.add('hidden');
      errorBox.innerText = '';
    }
  }

  async handleSaveContact(e) {
    e.preventDefault();
    const idInput = document.getElementById('contactIdInput');
    const nameInput = document.getElementById('contactNameInput');
    const phoneInput = document.getElementById('contactPhoneInput');
    const relInput = document.getElementById('contactRelInput');
    const isPrimaryInput = document.getElementById('contactIsPrimaryInput');
    const enabledInput = document.getElementById('contactEnabledInput');
    const errorBox = document.getElementById('contactFormError');
    const saveBtn = document.getElementById('saveContactBtn');

    const contactId = idInput ? idInput.value.trim() : '';
    const name = nameInput ? nameInput.value.trim() : '';
    const phone = phoneInput ? phoneInput.value.trim() : '';
    const relationship = relInput ? relInput.value.trim() : '';
    const isPrimary = isPrimaryInput ? isPrimaryInput.checked : false;
    const enabled = enabledInput ? enabledInput.checked : true;

    // Validation checks
    if (!name) {
      if (errorBox) {
        errorBox.innerText = 'Name is required.';
        errorBox.classList.remove('hidden');
      }
      return;
    }
    if (!phone) {
      if (errorBox) {
        errorBox.innerText = 'Phone number is required.';
        errorBox.classList.remove('hidden');
      }
      return;
    }
    if (!relationship) {
      if (errorBox) {
        errorBox.innerText = 'Relationship is required.';
        errorBox.classList.remove('hidden');
      }
      return;
    }

    const payload = {
      name,
      phone,
      relationship,
      is_primary: isPrimary,
      enabled: enabled
    };

    const isEdit = !!contactId;
    const endpoint = isEdit ? `/api/contacts/${contactId}` : '/api/contacts';
    const method = isEdit ? 'PUT' : 'POST';

    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.innerText = 'Saving...';
    }

    try {
      const result = await apiRequest(endpoint, {
        method,
        body: JSON.stringify(payload),
        timeout: 7000
      });

      if (result && result.status === 'success') {
        this.hideContactForm();
        await this.fetchEmergencyContacts();
        this.showToast(isEdit ? 'Contact updated successfully' : 'Contact saved successfully');
      } else {
        const errorMsg = (result && result.message) || 'Unable to save emergency contact.';
        if (errorBox) {
          errorBox.innerText = errorMsg;
          errorBox.classList.remove('hidden');
        }
        this.showToast('Unable to save emergency contact.');
      }
    } catch (err) {
      console.warn('Save contact failed:', err);
      const errorMsg = err.message || 'Unable to save emergency contact.';
      if (errorBox) {
        errorBox.innerText = errorMsg;
        errorBox.classList.remove('hidden');
      }
      this.showToast('Unable to save emergency contact.');
    } finally {
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.innerText = 'Save Contact';
      }
    }
  }

  promptDeleteContact(contactId) {
    const confirmBox = document.getElementById('contactDeleteConfirm');
    const nameEl = document.getElementById('deleteContactName');
    const contact = this.emergencyContacts.find(c => c.id === contactId);

    this.pendingDeleteContactId = contactId;
    if (nameEl) {
      nameEl.innerText = contact ? contact.name : 'this contact';
    }
    if (confirmBox) {
      confirmBox.classList.remove('hidden');
    }
  }

  cancelDeleteContact() {
    this.pendingDeleteContactId = null;
    const confirmBox = document.getElementById('contactDeleteConfirm');
    if (confirmBox) {
      confirmBox.classList.add('hidden');
    }
  }

  async confirmDeleteContact() {
    if (!this.pendingDeleteContactId) return;
    const idToDelete = this.pendingDeleteContactId;
    const confirmBtn = document.getElementById('confirmDeleteContactBtn');

    if (confirmBtn) {
      confirmBtn.disabled = true;
      confirmBtn.innerText = 'Deleting...';
    }

    try {
      const result = await apiRequest(`/api/contacts/${idToDelete}`, {
        method: 'DELETE',
        timeout: 7000
      });

      if (result && result.status === 'success') {
        this.cancelDeleteContact();
        await this.fetchEmergencyContacts();
        this.showToast('Contact deleted successfully');
      } else {
        this.cancelDeleteContact();
        this.showToast('Unable to delete emergency contact.');
      }
    } catch (err) {
      console.warn('Delete contact failed:', err);
      this.cancelDeleteContact();
      this.showToast('Unable to delete emergency contact.');
    } finally {
      if (confirmBtn) {
        confirmBtn.disabled = false;
        confirmBtn.innerText = 'Delete Contact';
      }
    }
  }

  escapeHtml(str) {
    const div = document.createElement('div');
    div.innerText = str;
    return div.innerHTML;
  }
}

// Instantiate on DOM load
document.addEventListener('DOMContentLoaded', () => {
  window.safeHerApp = new SafeHerApp();
});
