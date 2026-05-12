import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getBoardById } from "../api/boards";
import { PinDetailModal } from "../components/PinDetailModal";
import { PinGrid } from "../components/PinGrid";
import { AccountButton } from "../components/AccountButton";
import { useAuth } from "../context/useAuth";

export function BoardPage() {
  const { boardId = "" } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, logout } = useAuth();
  const [selectedPinId, setSelectedPinId] = useState<string | null>(null);

  const boardQuery = useQuery({
    queryKey: ["board", boardId],
    queryFn: () => getBoardById(boardId),
    enabled: Boolean(boardId),
  });

  if (boardQuery.isLoading) {
    return <div className="page-loading">Loading board...</div>;
  }

  if (boardQuery.isError || !boardQuery.data) {
    return (
      <div className="full-page-state">
        <h1>Board unavailable</h1>
        <p>This board may be private or no longer exist.</p>
        <Link className="btn btn-red" to="/">Go home</Link>
      </div>
    );
  }

  const board = boardQuery.data;

  return (
    <div>
      <header className="header">
        <Link className="header-logo" to="/" aria-label="Home">P</Link>
        <div className="header-page-title">Board</div>
        <Link className="btn btn-outline" to={`/users/${board.user.username}`}>
          View owner
        </Link>
        {isAuthenticated ? (
          <button className="btn btn-outline" onClick={logout}>Logout</button>
        ) : null}
        <AccountButton />
      </header>

      <main className="board-page">
        <section className="board-hero">
          <span className="board-visibility">{board.visibility}</span>
          <h1>{board.title}</h1>
          {board.description && <p>{board.description}</p>}
          <Link className="board-owner" to={`/users/${board.user.username}`}>
            <span className="header-avatar" style={{ width: 32, height: 32, fontSize: 12 }}>
              {board.user.avatar_url ? <img src={board.user.avatar_url} alt="" /> : board.user.username[0]}
            </span>
            {board.user.full_name || board.user.username}
          </Link>
        </section>

        <PinGrid
          pins={board.pins}
          isLoading={false}
          onPinClick={(pin) => isAuthenticated ? setSelectedPinId(pin.id) : navigate("/auth")}
        />
      </main>

      {selectedPinId && (
        <PinDetailModal
          pinId={selectedPinId}
          onClose={() => setSelectedPinId(null)}
          onPinSelect={(id) => setSelectedPinId(id)}
        />
      )}
    </div>
  );
}
