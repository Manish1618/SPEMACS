import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import type { MapEvent } from '../../types';
import { Satellite, Shield, Crosshair, Play, Pause, Layers, Eye } from 'lucide-react';

interface InvestigatorMapProps {
  events: MapEvent[];
  selectedEventId: string | null;
  onSelectEvent: (event: MapEvent | null) => void;
  highlightedCoords?: number[][];
}

export const InvestigatorMap: React.FC<InvestigatorMapProps> = ({
  events,
  selectedEventId,
  onSelectEvent,
  highlightedCoords
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const baseTileLayerRef = useRef<L.TileLayer | null>(null);
  const overlayTileLayerRef = useRef<L.TileLayer | null>(null);
  const markersRef = useRef<{ [id: string]: L.Marker }>({});
  const polylineRef = useRef<L.Polyline | null>(null);
  const animatedVehicleMarkerRef = useRef<L.Marker | null>(null);

  // Default to Real Satellite Hybrid Mode
  const [mapStyle, setMapStyle] = useState<'satellite' | 'dark' | 'topo'>('satellite');
  const [isLiveSimulating, setIsLiveSimulating] = useState(false);
  const [showLabels, setShowLabels] = useState(true);

  // 100% Free High-Res Imagery & Overlays (Zero API Key)
  const tileProviders = {
    satellite: {
      base: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      overlay: 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
      attrib: '&copy; Esri World Imagery &mdash; DigitalGlobe, Earthstar Geographics'
    },
    dark: {
      base: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
      overlay: null,
      attrib: '&copy; OpenStreetMap contributors &copy; CARTO'
    },
    topo: {
      base: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
      overlay: null,
      attrib: '&copy; Esri &mdash; National Geographic, DeLorme, NAVTEQ'
    }
  };

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (mapRef.current) {
      try {
        mapRef.current.remove();
      } catch (e) {
        console.warn('Map cleanup warning:', e);
      }
      mapRef.current = null;
    }

    // Reset container leaflet id if any
    (mapContainerRef.current as any)._leaflet_id = null;

    const map = L.map(mapContainerRef.current, {
      center: [28.56, 77.14], // Delhi NCR Airport & Aerocity
      zoom: 12,
      zoomControl: false,
      maxZoom: 19
    });

    const activeTile = tileProviders[mapStyle];

    // High-Res Satellite Base
    const baseLayer = L.tileLayer(activeTile.base, {
      attribution: activeTile.attrib,
      maxZoom: 19,
      subdomains: 'abcd'
    }).addTo(map);
    baseTileLayerRef.current = baseLayer;

    // Road & Place Label Overlay for Satellite
    if (activeTile.overlay && showLabels) {
      const overlayLayer = L.tileLayer(activeTile.overlay, {
        maxZoom: 19,
        subdomains: 'abcd'
      }).addTo(map);
      overlayTileLayerRef.current = overlayLayer;
    }

    L.control.zoom({ position: 'topright' }).addTo(map);
    mapRef.current = map;

    return () => {
      if (mapRef.current) {
        try {
          mapRef.current.remove();
        } catch (e) {
          console.warn('Map unmount cleanup:', e);
        }
        mapRef.current = null;
      }
    };
  }, []);


  // Handle Map Style / Overlay Switching
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (baseTileLayerRef.current) baseTileLayerRef.current.remove();
    if (overlayTileLayerRef.current) overlayTileLayerRef.current.remove();

    const activeTile = tileProviders[mapStyle];

    const baseLayer = L.tileLayer(activeTile.base, {
      attribution: activeTile.attrib,
      maxZoom: 19,
      subdomains: 'abcd'
    }).addTo(map);
    baseTileLayerRef.current = baseLayer;

    if (activeTile.overlay && showLabels) {
      const overlayLayer = L.tileLayer(activeTile.overlay, {
        maxZoom: 19,
        subdomains: 'abcd'
      }).addTo(map);
      overlayTileLayerRef.current = overlayLayer;
    }
  }, [mapStyle, showLabels]);

  // Update Markers & Glowing Forensic Trajectories
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    Object.values(markersRef.current).forEach(m => m.remove());
    markersRef.current = {};
    if (polylineRef.current) {
      polylineRef.current.remove();
      polylineRef.current = null;
    }

    if (events.length === 0) return;

    const latLngs: L.LatLngExpression[] = [];

    events.forEach(evt => {
      latLngs.push([evt.latitude, evt.longitude]);

      const isSelected = evt.event_id === selectedEventId;
      const markerColor = evt.event_type.includes('MEETING') 
        ? '#EF4444' // Red
        : (evt.event_type.includes('TRANSACTION') ? '#10B981' : (evt.event_type.includes('TOLL') ? '#F59E0B' : '#3B82F6'));

      const customIcon = L.divIcon({
        className: 'satellite-tactical-pin',
        html: `
          <div style="
            background-color: ${markerColor};
            width: ${isSelected ? '28px' : '20px'};
            height: ${isSelected ? '28px' : '20px'};
            border-radius: 50%;
            border: ${isSelected ? '3px solid #FFFFFF' : '2px solid #000000'};
            box-shadow: 0 0 ${isSelected ? '25px' : '12px'} ${markerColor}, inset 0 0 4px #FFFFFF;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
          ">
            <div style="width: 6px; height: 6px; background: white; border-radius: 50%;"></div>
            ${isSelected ? `
              <div style="
                position: absolute;
                inset: -8px;
                border-radius: 50%;
                border: 2px solid ${markerColor};
                animation: ping 1.2s cubic-bezier(0, 0, 0.2, 1) infinite;
              "></div>
            ` : ''}
          </div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 16]
      });

      const marker = L.marker([evt.latitude, evt.longitude], { icon: customIcon }).addTo(map);

      const popupHtml = `
        <div style="padding: 6px; font-family: ui-sans-serif, system-ui; min-width: 200px; background: #111827; color: #FFF; border-radius: 8px;">
          <div style="font-size: 10px; font-weight: bold; color: ${markerColor}; text-transform: uppercase; letter-spacing: 0.05em;">
            🛰️ SATELLITE RECON: ${evt.event_type.replace(/_/g, ' ')}
          </div>
          <div style="font-size: 13px; font-weight: bold; color: #FFFFFF; margin-top: 3px; line-height: 1.2;">
            ${evt.title}
          </div>
          <div style="font-size: 11px; color: #D1D5DB; margin-top: 5px;">
            📍 ${evt.location_name}
          </div>
          <div style="font-size: 10px; color: #93C5FD; margin-top: 3px; font-family: monospace;">
            🕒 ${new Date(evt.timestamp).toLocaleString()}
          </div>
          <div style="font-size: 10px; color: #34D399; margin-top: 6px; font-family: monospace; background: rgba(16, 185, 129, 0.2); padding: 2px 6px; border-radius: 4px; display: inline-block;">
            🛡️ Evidence: ${evt.evidence_id || 'AUTHENTICATED'}
          </div>
        </div>
      `;
      marker.bindPopup(popupHtml);

      marker.on('click', () => {
        onSelectEvent(evt);
      });

      markersRef.current[evt.event_id] = marker;
    });

    // Draw glowing satellite trajectory path
    if (latLngs.length > 1) {
      polylineRef.current = L.polyline(latLngs, {
        color: '#F59E0B',
        weight: 3.5,
        opacity: 0.9,
        dashArray: '8, 12'
      }).addTo(map);
    }
  }, [events, selectedEventId, mapStyle, showLabels]);

  // Handle Zoom to Highlighted Coords
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (highlightedCoords && highlightedCoords.length > 0) {
      const bounds = L.latLngBounds(highlightedCoords.map(c => [c[0], c[1]]));
      map.fitBounds(bounds, { padding: [70, 70], maxZoom: 15 });
    }
  }, [highlightedCoords]);

  // Live GPS Real-Time Simulation Loop
  useEffect(() => {
    let timer: any = null;
    let localIndex = 0;

    if (isLiveSimulating && events.length > 0 && mapRef.current) {
      const map = mapRef.current;

      timer = setInterval(() => {
        localIndex = (localIndex + 1) % events.length;
        const currentEvt = events[localIndex];

        if (animatedVehicleMarkerRef.current) {
          animatedVehicleMarkerRef.current.remove();
        }

        const vehicleIcon = L.divIcon({
          className: 'live-satellite-gps-marker',
          html: `
            <div style="
              background: #F59E0B;
              color: #000;
              width: 36px;
              height: 36px;
              border-radius: 50%;
              border: 3px solid #FFF;
              box-shadow: 0 0 30px #F59E0B, 0 0 10px #FFF;
              display: flex;
              align-items: center;
              justify-content: center;
              font-weight: bold;
              font-size: 16px;
              position: relative;
            ">
              🚗
              <div style="
                position: absolute;
                inset: -10px;
                border-radius: 50%;
                border: 2px solid #F59E0B;
                animation: ping 1s cubic-bezier(0, 0, 0.2, 1) infinite;
              "></div>
            </div>
          `,
          iconSize: [40, 40],
          iconAnchor: [20, 20]
        });

        const vehicleMarker = L.marker([currentEvt.latitude, currentEvt.longitude], { icon: vehicleIcon }).addTo(map);
        animatedVehicleMarkerRef.current = vehicleMarker;

        onSelectEvent(currentEvt);
        map.panTo([currentEvt.latitude, currentEvt.longitude], { animate: true, duration: 1.2 });
      }, 2500);
    }

    return () => {
      if (timer) clearInterval(timer);
      if (!isLiveSimulating && animatedVehicleMarkerRef.current) {
        animatedVehicleMarkerRef.current.remove();
        animatedVehicleMarkerRef.current = null;
      }
    };
  }, [isLiveSimulating, events]);

  const selectedEventObj = events.find(e => e.event_id === selectedEventId);

  const jumpToRegion = (lat: number, lon: number, zoom: number) => {
    mapRef.current?.setView([lat, lon], zoom, { animate: true });
  };

  return (
    <div className="relative w-full h-full bg-dark-950 overflow-hidden flex flex-col">
      {/* Top Left: Map HUD Header */}
      <div className="absolute top-3 left-3 z-20 flex items-center space-x-2">
        <div className="bg-dark-900/90 backdrop-blur-md px-3 py-1.5 rounded-lg border border-amber-500/40 shadow-2xl flex items-center space-x-2">
          <Satellite className="w-4 h-4 text-amber-400" />
          <span className="text-xs font-bold text-white tracking-wide">Real Satellite Reconnaissance</span>
          <span className="text-[10px] bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded font-mono font-bold border border-amber-500/30">
            High-Res Imagery
          </span>
        </div>

        {/* Live GPS Trajectory Simulation Button */}
        <button
          onClick={() => setIsLiveSimulating(!isLiveSimulating)}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all shadow-2xl border ${
            isLiveSimulating
              ? 'bg-amber-500 text-black border-amber-300 animate-pulse'
              : 'bg-dark-900/90 text-amber-400 border-gray-700 hover:bg-dark-800 hover:text-white'
          }`}
        >
          {isLiveSimulating ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
          <span>{isLiveSimulating ? 'Tracking Active' : 'Live GPS Playback'}</span>
        </button>
      </div>

      {/* Top Right: Layer Switcher & Overlays */}
      <div className="absolute top-3 right-3 z-20 flex items-center space-x-2">
        {/* Layer Switcher */}
        <div className="bg-dark-900/90 backdrop-blur-md p-1 rounded-lg border border-gray-700 shadow-2xl flex items-center space-x-1">
          <button
            onClick={() => setMapStyle('satellite')}
            className={`px-2.5 py-1 rounded text-[11px] font-bold transition-all flex items-center space-x-1.5 ${
              mapStyle === 'satellite' ? 'bg-amber-600 text-white shadow-lg' : 'text-gray-400 hover:text-white'
            }`}
            title="Real Satellite Imagery View"
          >
            <Satellite className="w-3.5 h-3.5 text-amber-300" />
            <span>Satellite</span>
          </button>
          <button
            onClick={() => setMapStyle('dark')}
            className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all flex items-center space-x-1 ${
              mapStyle === 'dark' ? 'bg-indigo-600 text-white shadow' : 'text-gray-400 hover:text-white'
            }`}
            title="Dark Tactical Mode"
          >
            <Shield className="w-3 h-3" />
            <span>Dark</span>
          </button>
          <button
            onClick={() => setMapStyle('topo')}
            className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all flex items-center space-x-1 ${
              mapStyle === 'topo' ? 'bg-indigo-600 text-white shadow' : 'text-gray-400 hover:text-white'
            }`}
            title="Topographic Terrain"
          >
            <Layers className="w-3 h-3 text-emerald-300" />
            <span>Topo</span>
          </button>
        </div>

        {/* Toggle Labels */}
        {mapStyle === 'satellite' && (
          <button
            onClick={() => setShowLabels(!showLabels)}
            className={`px-2.5 py-1.5 rounded-lg text-[10px] font-bold transition-all border shadow-2xl flex items-center space-x-1 ${
              showLabels ? 'bg-indigo-600/80 text-white border-indigo-400' : 'bg-dark-900/90 text-gray-400 border-gray-700 hover:text-white'
            }`}
            title="Toggle Road & City Labels"
          >
            <Eye className="w-3 h-3" />
            <span>Labels</span>
          </button>
        )}

        {/* Quick Region Jumps */}
        <div className="bg-dark-900/90 backdrop-blur-md p-1 rounded-lg border border-gray-700 shadow-2xl flex items-center space-x-1">
          <button
            onClick={() => jumpToRegion(28.56, 77.14, 13)}
            className="px-2 py-1 rounded text-[10px] font-bold text-gray-300 hover:text-white hover:bg-gray-700"
          >
            Aerocity Delhi
          </button>
          <button
            onClick={() => jumpToRegion(18.96, 72.90, 12)}
            className="px-2 py-1 rounded text-[10px] font-bold text-gray-300 hover:text-white hover:bg-gray-700"
          >
            Mumbai Port
          </button>
        </div>
      </div>

      {/* Main Leaflet Satellite Map View */}
      <div ref={mapContainerRef} className="w-full h-full" />

      {/* Bottom Floating Telemetry HUD */}
      {selectedEventObj && (
        <div className="absolute bottom-3 left-3 right-3 z-20 bg-dark-900/95 backdrop-blur-md border border-amber-500/40 rounded-xl p-3 shadow-2xl flex items-center justify-between">
          <div className="flex items-center space-x-3.5">
            <div className="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center">
              <Crosshair className="w-4 h-4 text-amber-400" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xs font-bold text-white">{selectedEventObj.title}</span>
                <span className="text-[10px] bg-amber-500/20 text-amber-300 font-mono px-1.5 py-0.5 rounded border border-amber-500/30">
                  {selectedEventObj.event_id}
                </span>
              </div>
              <div className="text-[11px] text-gray-300 flex items-center space-x-3 mt-0.5 font-mono">
                <span>📍 Lat: <strong className="text-amber-300">{selectedEventObj.latitude.toFixed(4)}</strong>, Lon: <strong className="text-amber-300">{selectedEventObj.longitude.toFixed(4)}</strong></span>
                <span>•</span>
                <span>Location: <strong className="text-white">{selectedEventObj.location_name}</strong></span>
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-3 font-mono text-xs">
            <div className="text-right">
              <div className="text-[10px] text-gray-400">Forensic Grounding:</div>
              <div className="text-emerald-400 font-bold">
                {new Date(selectedEventObj.timestamp).toLocaleDateString()} {new Date(selectedEventObj.timestamp).toLocaleTimeString()}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
