import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getCurrentUser, getPublicUser, getUserBoards, getUserPins, updateCurrentUser } from "../api/users";
import type { UserUpdate } from "../api/users";
import { getApiErrorMessage } from "../api/clients";
import { AccountButton } from "../components/AccountButton";
import { PinDetailModal } from "../components/PinDetailModal";
import { PinGrid } from "../components/PinGrid";
import { useAuth } from "../context/useAuth";
import type { UserResponse } from "../types/api";

type ProfileTab = "pins" | "boards";

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "long",
    year: "numeric",
  }).format(new Date(value));
}

export function UserPage() {
  const { username = "" } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, logout } = useAuth();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<ProfileTab>("pins");
  const [isEditing, setIsEditing] = useState(false);
  const [selectedPinId, setSelectedPinId] = useState<string | null>(null);

  const profileQuery = useQuery({
    queryKey: ["publicUser", username],
    queryFn: () => getPublicUser(username),
    enabled: Boolean(username),
  });

  const pinsQuery = useQuery({
    queryKey: ["userPins", username],
    queryFn: () => getUserPins(username),
    enabled: Boolean(username),
  });

  const boardsQuery = useQuery({
    queryKey: ["userBoards", username],
    queryFn: () => getUserBoards(username),
    enabled: Boolean(username),
  });

  const currentUserQuery = useQuery({
    queryKey: ["currentUser"],
    queryFn: getCurrentUser,
    enabled: isAuthenticated,
    staleTime: 60_000,
  });

  const updateProfileMutation = useMutation({
    mutationFn: updateCurrentUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["currentUser"] });
      queryClient.invalidateQueries({ queryKey: ["publicUser", username] });
      setIsEditing(false);
    },
  });

  if (profileQuery.isLoading) {
    return <div className="page-loading">Loading profile...</div>;
  }

  if (profileQuery.isError || !profileQuery.data) {
    return (
      <div className="full-page-state">
        <h1>User not found</h1>
        <p>This profile does not exist or is unavailable.</p>
        <Link className="btn btn-red" to="/">Go home</Link>
      </div>
    );
  }

  const user = profileQuery.data;
  const displayName = user.full_name || user.username;
  const isOwnProfile = currentUserQuery.data?.username === user.username;
  const editError = updateProfileMutation.error
    ? getApiErrorMessage(updateProfileMutation.error, "Failed to update profile")
    : null;

  return (
    <div>
      <header className="header">
        <Link className="header-logo" to="/" aria-label="Home">P</Link>
        <div className="header-page-title">Profile</div>
        <Link className="btn btn-outline" to="/">Home</Link>
        {isAuthenticated ? (
          <button className="btn btn-outline" onClick={logout}>Logout</button>
        ) : null}
        <AccountButton />
      </header>

      <main className="profile-page">
        <section className="profile-hero">
          <div className="profile-avatar">
            {user.avatar_url ? <img src={user.avatar_url} alt="" /> : user.username[0]}
          </div>
          <h1>{displayName}</h1>
          <p className="profile-username">@{user.username}</p>
          {user.bio && <p className="profile-bio">{user.bio}</p>}
          <p className="profile-joined">Joined {formatDate(user.created_at)}</p>
          <div className="profile-stats">
            <span><strong>{user.pins_count}</strong> Pins</span>
            <span><strong>{user.boards_count}</strong> Boards</span>
          </div>
          {isOwnProfile && (
            <button className="btn btn-outline profile-edit-btn" onClick={() => setIsEditing(true)}>
              Edit profile
            </button>
          )}
        </section>

        <div className="profile-tabs">
          <button
            className={activeTab === "pins" ? "profile-tab active" : "profile-tab"}
            onClick={() => setActiveTab("pins")}
          >
            Pins
          </button>
          <button
            className={activeTab === "boards" ? "profile-tab active" : "profile-tab"}
            onClick={() => setActiveTab("boards")}
          >
            Boards
          </button>
        </div>

        {activeTab === "pins" ? (
          pinsQuery.isError ? (
            <div className="empty-state">Could not load pins.</div>
          ) : (
            <PinGrid
              pins={pinsQuery.data ?? []}
              isLoading={pinsQuery.isLoading}
              onPinClick={(pin) => isAuthenticated ? setSelectedPinId(pin.id) : navigate("/auth")}
            />
          )
        ) : boardsQuery.isError ? (
          <div className="empty-state">Could not load boards.</div>
        ) : boardsQuery.isLoading ? (
          <div className="page-loading">Loading boards...</div>
        ) : boardsQuery.data?.length ? (
          <div className="board-grid">
            {boardsQuery.data.map((board) => (
              <Link className="board-card" key={board.id} to={`/boards/${board.id}`}>
                <div>
                  <h3>{board.title}</h3>
                  {board.description && <p>{board.description}</p>}
                </div>
                <span className="board-visibility">{board.visibility}</span>
              </Link>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <h2>No boards yet</h2>
            <p>This user has no visible boards.</p>
          </div>
        )}
      </main>

      {selectedPinId && (
        <PinDetailModal
          pinId={selectedPinId}
          onClose={() => setSelectedPinId(null)}
          onPinSelect={(id) => setSelectedPinId(id)}
        />
      )}

      {isEditing && currentUserQuery.data && (
        <EditProfileModal
          user={currentUserQuery.data}
          isPending={updateProfileMutation.isPending}
          error={typeof editError === "string" ? editError : null}
          onClose={() => setIsEditing(false)}
          onSubmit={(data) => updateProfileMutation.mutate(data)}
        />
      )}
    </div>
  );
}

interface EditProfileModalProps {
  user: UserResponse;
  isPending: boolean;
  error?: string | null;
  onClose: () => void;
  onSubmit: (data: UserUpdate) => void;
}

function EditProfileModal({ user, isPending, error, onClose, onSubmit }: EditProfileModalProps) {
  const [fullName, setFullName] = useState(user.full_name ?? "");
  const [bio, setBio] = useState(user.bio ?? "");
  const [avatarUrl, setAvatarUrl] = useState(user.avatar_url ?? "");
  const [emailNotificationsEnabled, setEmailNotificationsEnabled] = useState(
    user.email_notifications_enabled
  );

  useEffect(() => {
    setFullName(user.full_name ?? "");
    setBio(user.bio ?? "");
    setAvatarUrl(user.avatar_url ?? "");
    setEmailNotificationsEnabled(user.email_notifications_enabled);
  }, [user]);

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    onSubmit({
      full_name: fullName.trim() || null,
      bio: bio.trim() || null,
      avatar_url: avatarUrl.trim() || null,
      email_notifications_enabled: emailNotificationsEnabled,
    });
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card profile-edit-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 style={{ margin: 0, fontSize: 18 }}>Edit profile</h2>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close">x</button>
        </div>

        <form className="modal-fields" onSubmit={handleSubmit}>
          {error && <div className="form-error">{error}</div>}

          <div className="profile-edit-preview">
            <div className="profile-avatar">
              {avatarUrl ? <img src={avatarUrl} alt="" /> : user.username[0]}
            </div>
            <div>
              <strong>@{user.username}</strong>
              <p>Public profile preview</p>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="profile-full-name">Full name</label>
            <input
              id="profile-full-name"
              className="form-input"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              maxLength={100}
            />
          </div>

          <div className="form-group">
            <label htmlFor="profile-bio">Bio</label>
            <textarea
              id="profile-bio"
              className="form-input"
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              rows={4}
              maxLength={200}
              style={{ resize: "vertical", height: "auto", paddingTop: 10 }}
            />
          </div>

          <div className="form-group">
            <label htmlFor="profile-avatar-url">Avatar URL</label>
            <input
              id="profile-avatar-url"
              className="form-input"
              type="url"
              value={avatarUrl}
              onChange={(e) => setAvatarUrl(e.target.value)}
              placeholder="https://example.com/avatar.jpg"
            />
          </div>

          <label className="checkbox-row" htmlFor="profile-email-notifications">
            <input
              id="profile-email-notifications"
              type="checkbox"
              checked={emailNotificationsEnabled}
              onChange={(e) => setEmailNotificationsEnabled(e.target.checked)}
            />
            <span>Email notifications</span>
          </label>

          <div className="profile-edit-actions">
            <button type="button" className="btn btn-outline" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-red" disabled={isPending}>
              {isPending ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
