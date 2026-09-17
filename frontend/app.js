// Talks to Elasticsearch directly from the browser (CORS enabled on the
// ES container for exactly this) instead of going through Kibana - this
// page is a standalone alternative view of the same live data.

const ELASTICSEARCH_URL = "http://localhost:9200";
const INDEX = "vehicle-positions";
const REFRESH_MS = 15000;

const ROUTE_COLORS = {
  bus: "#c51616",
  streetcar: "#610dfb",
};

const map = L.map("map").setView([43.7, -79.4], 11);

L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
  maxZoom: 19,
}).addTo(map);

let markersLayer = L.layerGroup().addTo(map);

async function fetchVehicles() {
  // collapse on vehicle_id + sort by @timestamp desc: one marker per
  // vehicle at its most recent known position, not one per historical
  // poll within the window.
  const body = {
    size: 3000,
    query: { range: { "@timestamp": { gte: "now-2m" } } },
    sort: [{ "@timestamp": "desc" }],
    collapse: { field: "vehicle_id" },
  };

  const response = await fetch(`${ELASTICSEARCH_URL}/${INDEX}/_search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Elasticsearch query failed: ${response.status}`);
  }

  const data = await response.json();
  return data.hits.hits.map((hit) => hit._source);
}

function render(vehicles) {
  markersLayer.clearLayers();

  let busCount = 0;
  let streetcarCount = 0;

  for (const v of vehicles) {
    if (!v.location) continue;
    if (v.route_type === "bus") busCount++;
    else if (v.route_type === "streetcar") streetcarCount++;

    const color = ROUTE_COLORS[v.route_type] || "#888";
    const marker = L.circleMarker([v.location.lat, v.location.lon], {
      radius: 5,
      color,
      fillColor: color,
      fillOpacity: 0.85,
      weight: 1,
    });

    const speedKmh = (v.speed * 3.6).toFixed(0);
    marker.bindPopup(
      `<b>Route ${v.route_short_name}</b><br>` +
        `${v.route_type}<br>` +
        `Vehicle ${v.vehicle_id}<br>` +
        `${speedKmh} km/h`
    );

    marker.addTo(markersLayer);
  }

  document.getElementById("stats").textContent =
    `${vehicles.length} vehicles — ${busCount} bus, ${streetcarCount} streetcar`;
}

async function tick() {
  try {
    const vehicles = await fetchVehicles();
    render(vehicles);
  } catch (err) {
    document.getElementById("stats").textContent = "Error loading data - is Elasticsearch reachable?";
    console.error(err);
  }
}

tick();
setInterval(tick, REFRESH_MS);
