import type { Pin } from "../types/api";

interface PinCardProps {
  pin: Pin;
  onClick?: () => void;
}

export function PinCard({ pin, onClick }: PinCardProps) {
  return (
    <div className="pin-card" onClick={onClick}>
      <div style={{ position: "relative" }}>
        <img
          src={pin.image_url}
          alt={pin.title}
          loading="lazy"
        />
        <div className="pin-overlay">
          <button
            className="btn btn-red pin-save-btn"
            onClick={(e) => {
              e.stopPropagation();
            }}
          >
            Save
          </button>
        </div>
      </div>
      <div className="pin-info">
        <p className="pin-title">{pin.title}</p>
        {pin.description && <p className="pin-desc">{pin.description}</p>}
        {pin.tags.length > 0 && (
          <div style={{ marginTop: "6px" }}>
            {pin.tags.slice(0, 3).map((tag) => (
              <span key={tag.id} className="tag-chip">#{tag.name}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
