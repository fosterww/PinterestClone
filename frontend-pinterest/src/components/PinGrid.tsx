import type { Pin } from "../types/api";
import { PinCard } from "./PinCard";

const SKELETON_HEIGHTS = [280, 340, 210, 380, 260, 300, 220, 360, 290, 250];

interface PinGridProps {
  pins: Pin[];
  isLoading?: boolean;
  onPinClick?: (pin: Pin) => void;
}

export function PinGrid({ pins, isLoading, onPinClick }: PinGridProps) {
  if (isLoading) {
    return (
      <div className="pin-grid">
        {SKELETON_HEIGHTS.map((h, i) => (
          <div key={i} className="pin-skeleton" style={{ height: h }} />
        ))}
      </div>
    );
  }

  if (pins.length === 0) {
    return (
      <div className="empty-state">
        <div style={{ fontSize: 56, marginBottom: 16 }}>📌</div>
        <h2>No pins yet</h2>
        <p>Be the first to create a pin!</p>
      </div>
    );
  }

  return (
    <div className="pin-grid">
      {pins.map((pin) => (
        <PinCard 
          key={pin.id} 
          pin={pin} 
          onClick={() => onPinClick?.(pin)} 
        />
      ))}
    </div>
  );
}
