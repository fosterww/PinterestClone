import { useState } from "react";
import type { FormEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getPinDetail, getRelatedPins, likePin, unlikePin, addComment } from "../api/pins";
import { PinGrid } from "./PinGrid";

interface PinDetailModalProps {
  pinId: string;
  onClose: () => void;
  onPinSelect: (id: string) => void;
}

export function PinDetailModal({ pinId, onClose, onPinSelect }: PinDetailModalProps) {
  const queryClient = useQueryClient();
  const [commentText, setCommentText] = useState("");

  const { data: pin, isLoading, isError } = useQuery({
    queryKey: ["pin", pinId],
    queryFn: () => getPinDetail(pinId),
  });

  const { data: relatedPins, isLoading: isRelatedLoading } = useQuery({
    queryKey: ["relatedPins", pinId],
    queryFn: () => getRelatedPins(pinId),
  });

  const likeMutation = useMutation({
    mutationFn: (action: "like" | "unlike") => action === "like" ? likePin(pinId) : unlikePin(pinId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pin", pinId] });
      queryClient.invalidateQueries({ queryKey: ["pins"] });
    }
  });

  const commentMutation = useMutation({
    mutationFn: (text: string) => addComment(pinId, { comment: text }),
    onSuccess: () => {
      setCommentText("");
      queryClient.invalidateQueries({ queryKey: ["pin", pinId] });
    }
  });

  const handleLikeToggle = () => {
    likeMutation.mutate("like");
  };

  const handleCommentSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (commentText.trim()) {
      commentMutation.mutate(commentText.trim());
    }
  };

  if (isError) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="pdm-layout" onClick={e => e.stopPropagation()}>
        <button className="modal-close-btn pdm-close" onClick={onClose} aria-label="Close">✕</button>

        <div className="pdm-main">
          {isLoading || !pin ? (
            <div className="pdm-loading">Loading...</div>
          ) : (
            <div className="pdm-card">
              <div className="pdm-img-col">
                <img src={pin.image_url} alt={pin.title} />
              </div>
              <div className="pdm-info-col">
                <div className="pdm-top-bar">
                  <div className="pdm-user">
                    <div className="header-avatar" style={{ width: 32, height: 32, fontSize: 12 }}>
                      {pin.user?.username?.[0] || 'U'}
                    </div>
                    <span style={{ fontWeight: 600 }}>{pin.user?.username || 'Unknown User'}</span>
                  </div>
                  <button
                    className="btn btn-ghost"
                    onClick={handleLikeToggle}
                    disabled={likeMutation.isPending}
                  >
                    ❤️ {pin.likes_count}
                  </button>
                </div>

                <div className="pdm-desc-area">
                  <h1 className="pdm-title">{pin.title}</h1>
                  {pin.description && <p className="pdm-desc">{pin.description}</p>}
                </div>

                <div className="pdm-comments">
                  <h3>Comments</h3>
                  <div className="pdm-comments-list">
                    {pin.comments?.length === 0 && <p className="text-light">No comments yet</p>}
                    {pin.comments?.map(c => (
                      <div key={c.id} className="pdm-comment-item">
                        <span style={{ fontWeight: 600, marginRight: 8 }}>{c.user.username}</span>
                        <span>{c.comment}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pdm-add-comment">
                  <form onSubmit={handleCommentSubmit} style={{ display: "flex", gap: "8px" }}>
                    <input
                      type="text"
                      className="form-input"
                      style={{ height: 40 }}
                      placeholder="Add a comment"
                      value={commentText}
                      onChange={e => setCommentText(e.target.value)}
                      disabled={commentMutation.isPending}
                    />
                    <button
                      type="submit"
                      className="btn btn-red"
                      style={{ padding: "0 16px" }}
                      disabled={!commentText.trim() || commentMutation.isPending}
                    >
                      Post
                    </button>
                  </form>
                </div>

              </div>
            </div>
          )}
        </div>

        <div className="pdm-sidebar">
          <h3>Related Pins</h3>
          <PinGrid
            pins={relatedPins ?? []}
            isLoading={isRelatedLoading}
            onPinClick={(p) => onPinSelect(p.id)}
          />
        </div>

      </div>
    </div>
  );
}
