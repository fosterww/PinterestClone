import { useState, useRef } from "react";

interface CreatePinModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSubmit: (data: {
        title: string;
        description?: string;
        link_url?: string;
        tags?: string[];
        generate_ai_description?: boolean;
        image: File;
    }) => void;
    isPending: boolean;
    error?: string | null;
}

export function CreatePinModal({ isOpen, onClose, onSubmit, isPending, error }: CreatePinModalProps) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [preview, setPreview] = useState<string | null>(null);
    const [imageFile, setImageFile] = useState<File | null>(null);
    const [title, setTitle] = useState("");
    const [description, setDescription] = useState("");
    const [linkUrl, setLinkUrl] = useState("");
    const [tagsInput, setTagsInput] = useState("");
    const [generateAiDescription, setGenerateAiDescription] = useState(false);

    if (!isOpen) return null;

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setImageFile(file);
        setPreview(URL.createObjectURL(file));
    };

    const handleDescriptionChange = (value: string) => {
        setDescription(value);
        if (value.trim()) {
            setGenerateAiDescription(false);
        }
    };

    const handleClose = () => {
        setPreview(null);
        setImageFile(null);
        setTitle("");
        setDescription("");
        setLinkUrl("");
        setTagsInput("");
        setGenerateAiDescription(false);
        onClose();
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!imageFile) return;

        const tags = tagsInput
            .split(",")
            .map(t => t.trim())
            .filter(Boolean);

        onSubmit({
            title,
            description: description || undefined,
            link_url: linkUrl || undefined,
            tags: tags.length > 0 ? tags : undefined,
            generate_ai_description: generateAiDescription,
            image: imageFile,
        });
    };

    return (
        <div className="modal-backdrop" onClick={handleClose}>
            <div className="modal-card" onClick={e => e.stopPropagation()}>

                {/* Header */}
                <div className="modal-header">
                    <h2 style={{ margin: 0, fontSize: 18 }}>Create Pin</h2>
                    <button className="modal-close-btn" onClick={handleClose} aria-label="Close">✕</button>
                </div>

                <form onSubmit={handleSubmit} className="modal-body">
                    {/* Left: Image upload */}
                    <div
                        className="modal-upload-zone"
                        onClick={() => fileInputRef.current?.click()}
                        style={{ backgroundImage: preview ? `url(${preview})` : undefined }}
                    >
                        {!preview && (
                            <div className="modal-upload-placeholder">
                                <div style={{ fontSize: 40 }}>📷</div>
                                <p style={{ fontWeight: 600, margin: "8px 0 4px" }}>Choose a file</p>
                                <p style={{ fontSize: 12, color: "#767676", margin: 0 }}>JPEG, PNG, WEBP, GIF</p>
                            </div>
                        )}
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/jpeg,image/png,image/webp,image/gif"
                            style={{ display: "none" }}
                            onChange={handleFileChange}
                            required
                        />
                    </div>

                    {/* Right: Form fields */}
                    <div className="modal-fields">
                        {error && <div className="form-error">{error}</div>}

                        <div className="form-group">
                            <label htmlFor="pin-title">Title *</label>
                            <input
                                id="pin-title"
                                className="form-input"
                                type="text"
                                value={title}
                                onChange={e => setTitle(e.target.value)}
                                placeholder="Give your pin a title"
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="pin-desc">Description</label>
                            <textarea
                                id="pin-desc"
                                className="form-input"
                                value={description}
                                onChange={e => handleDescriptionChange(e.target.value)}
                                placeholder="Tell everyone about this pin"
                                rows={3}
                                style={{ resize: "vertical", height: "auto", paddingTop: 10 }}
                            />
                        </div>

                        <label className="checkbox-row" htmlFor="pin-ai-description">
                            <input
                                id="pin-ai-description"
                                type="checkbox"
                                checked={generateAiDescription}
                                onChange={e => setGenerateAiDescription(e.target.checked)}
                                disabled={Boolean(description.trim())}
                            />
                            <span>
                                Generate description with AI
                                <small>
                                    {description.trim()
                                        ? "Clear manual description to use AI generation."
                                        : "Gemini will write a short description from the image and title."}
                                </small>
                            </span>
                        </label>

                        <div className="form-group">
                            <label htmlFor="pin-link">Link</label>
                            <input
                                id="pin-link"
                                className="form-input"
                                type="url"
                                value={linkUrl}
                                onChange={e => setLinkUrl(e.target.value)}
                                placeholder="https://example.com"
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="pin-tags">Tags</label>
                            <input
                                id="pin-tags"
                                className="form-input"
                                type="text"
                                value={tagsInput}
                                onChange={e => setTagsInput(e.target.value)}
                                placeholder="travel, design, food  (comma separated)"
                            />
                        </div>

                        <button
                            type="submit"
                            className="btn btn-red"
                            disabled={isPending || !imageFile || !title}
                            style={{ width: "100%", justifyContent: "center", height: 48, fontSize: 16, marginTop: "auto" }}
                        >
                            {isPending ? "Publishing…" : "Publish"}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
