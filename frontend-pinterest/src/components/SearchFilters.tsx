import { useState, useRef, useEffect } from "react";
import type { KeyboardEvent } from "react";
import type { PinFilters, Popularity, CreatedAt } from "../types/api";

interface SearchFiltersProps {
    filters: PinFilters;
    onChange: (filters: PinFilters) => void;
}

const POPULARITY_OPTIONS: { label: string; value: Popularity }[] = [
    { label: "Most Popular", value: "Most Popular" },
    { label: "Least Popular", value: "Least Popular" },
];

const DATE_OPTIONS: { label: string; value: CreatedAt }[] = [
    { label: "Newest first", value: "Newest" },
    { label: "Oldest first", value: "Oldest" },
];

export function SearchFilters({ filters, onChange }: SearchFiltersProps) {
    const [open, setOpen] = useState(false);
    const [tagInput, setTagInput] = useState("");
    const panelRef = useRef<HTMLDivElement>(null);
    const btnRef = useRef<HTMLButtonElement>(null);

    // Close panel when clicking outside
    useEffect(() => {
        if (!open) return;
        function handleClick(e: MouseEvent) {
            if (
                panelRef.current &&
                !panelRef.current.contains(e.target as Node) &&
                btnRef.current &&
                !btnRef.current.contains(e.target as Node)
            ) {
                setOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClick);
        return () => document.removeEventListener("mousedown", handleClick);
    }, [open]);

    const tags = filters.tags ?? [];

    function addTag(raw: string) {
        const newTags = raw
            .split(",")
            .map((t) => t.trim().toLowerCase())
            .filter((t) => t && !tags.includes(t));
        if (newTags.length > 0) {
            onChange({ ...filters, tags: [...tags, ...newTags] });
        }
        setTagInput("");
    }

    function removeTag(tag: string) {
        const next = tags.filter((t) => t !== tag);
        onChange({ ...filters, tags: next.length > 0 ? next : undefined });
    }

    function handleTagKeyDown(e: KeyboardEvent<HTMLInputElement>) {
        if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            if (tagInput.trim()) addTag(tagInput);
        } else if (e.key === "Backspace" && tagInput === "" && tags.length > 0) {
            removeTag(tags[tags.length - 1]);
        }
    }

    function togglePopularity(val: Popularity) {
        onChange({
            ...filters,
            popularity: filters.popularity === val ? undefined : val,
        });
    }

    function toggleDate(val: CreatedAt) {
        onChange({
            ...filters,
            created_at: filters.created_at === val ? undefined : val,
        });
    }

    function clearAll() {
        onChange({});
        setTagInput("");
    }

    const activeCount =
        (filters.popularity ? 1 : 0) +
        (filters.created_at ? 1 : 0) +
        (tags.length > 0 ? 1 : 0);

    return (
        <div className="sf-root">
            <button
                ref={btnRef}
                className={`sf-trigger ${open ? "sf-trigger--open" : ""}`}
                onClick={() => setOpen((v) => !v)}
                aria-expanded={open}
                aria-label="Open filters"
                title="Filters"
                type="button"
            >
                <FilterIcon />
                {activeCount > 0 && (
                    <span className="sf-badge">{activeCount}</span>
                )}
            </button>

            {open && (
                <div ref={panelRef} className="sf-panel">
                    <div className="sf-panel-header">
                        <span className="sf-panel-title">Filters</span>
                        {activeCount > 0 && (
                            <button className="sf-clear-btn" onClick={clearAll}>
                                Clear all
                            </button>
                        )}
                    </div>

                    {/* Popularity */}
                    <div className="sf-section">
                        <p className="sf-section-label">Popularity</p>
                        <div className="sf-pills">
                            {POPULARITY_OPTIONS.map((opt) => (
                                <button
                                    key={opt.value}
                                    type="button"
                                    className={`sf-pill ${filters.popularity === opt.value ? "sf-pill--active" : ""}`}
                                    onClick={() => togglePopularity(opt.value)}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Date */}
                    <div className="sf-section">
                        <p className="sf-section-label">Date</p>
                        <div className="sf-pills">
                            {DATE_OPTIONS.map((opt) => (
                                <button
                                    key={opt.value}
                                    type="button"
                                    className={`sf-pill ${filters.created_at === opt.value ? "sf-pill--active" : ""}`}
                                    onClick={() => toggleDate(opt.value)}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Tags */}
                    <div className="sf-section">
                        <p className="sf-section-label">Tags</p>
                        <div className="sf-tag-input-wrap">
                            {tags.map((tag) => (
                                <span key={tag} className="sf-tag-chip">
                                    {tag}
                                    <button
                                        type="button"
                                        className="sf-tag-remove"
                                        onClick={() => removeTag(tag)}
                                        aria-label={`Remove tag ${tag}`}
                                    >
                                        ×
                                    </button>
                                </span>
                            ))}
                            <input
                                className="sf-tag-field"
                                type="text"
                                placeholder={tags.length === 0 ? "Add tags…" : ""}
                                value={tagInput}
                                onChange={(e) => setTagInput(e.target.value)}
                                onKeyDown={handleTagKeyDown}
                                onBlur={() => {
                                    if (tagInput.trim()) addTag(tagInput);
                                }}
                            />
                        </div>
                        <p className="sf-hint">Press Enter or comma to add</p>
                    </div>
                </div>
            )}
        </div>
    );
}

function FilterIcon() {
    return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="4" y1="6" x2="20" y2="6" />
            <line x1="8" y1="12" x2="16" y2="12" />
            <line x1="11" y1="18" x2="13" y2="18" />
        </svg>
    );
}
