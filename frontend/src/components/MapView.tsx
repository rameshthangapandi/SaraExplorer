import L from "leaflet";
import { useEffect } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";

export type Pin = { lat: number; lon: number; title: string; subtitle?: string; kind: string; href?: string };

const COLORS: Record<string, string> = {
  center: "#0b0b0b",
  attractions: "#e3a812",
  restaurants: "#d9480f",
  cafes: "#8a5a2b",
  stays: "#1c7ed6",
  me: "#2f9e44",
};

function icon(kind: string, active = false) {
  const c = COLORS[kind] ?? "#e3a812";
  const size = kind === "center" || active ? 30 : 22;
  return L.divIcon({
    className: "",
    iconSize: [size, size],
    iconAnchor: [size / 2, size],
    popupAnchor: [0, -size],
    html: `<div style="width:${size}px;height:${size}px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:${c};border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.35)"></div>`,
  });
}

function Recenter({ lat, lon, zoom }: { lat: number; lon: number; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView([lat, lon], zoom);
  }, [lat, lon, zoom, map]);
  return null;
}

export default function MapView({ center, pins, zoom = 13, activeIndex, className = "h-80" }: {
  center: { lat: number; lon: number };
  pins: Pin[];
  zoom?: number;
  activeIndex?: number | null;
  className?: string;
}) {
  return (
    <div className={`overflow-hidden rounded-2xl border border-ink-100 ${className}`}>
      <MapContainer center={[center.lat, center.lon]} zoom={zoom} scrollWheelZoom={false} className="h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />
        <Recenter lat={center.lat} lon={center.lon} zoom={zoom} />
        {pins.map((p, i) => (
          <Marker key={`${p.kind}-${i}-${p.lat}`} position={[p.lat, p.lon]} icon={icon(p.kind, i === activeIndex)} zIndexOffset={i === activeIndex ? 1000 : 0}>
            <Popup>
              <div className="text-sm font-semibold">{p.title}</div>
              {p.subtitle && <div className="text-xs text-ink-500">{p.subtitle}</div>}
              {p.href && <a href={p.href} target="_blank" rel="noopener noreferrer" className="text-xs font-semibold">Open in Google Maps →</a>}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
