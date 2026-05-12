import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { searchAll } from "../api/search";
import { PinDetailModal } from "../components/PinDetailModal";
import { PinGrid } from "../components/PinGrid";
import { AccountButton } from "../components/AccountButton";
import { useAuth } from "../context/useAuth";
import type { SearchTarget } from "../types/api";

const SEARCH_TARGETS: { label: string; value: SearchTarget }[] = [
  { label: "All", value: "all" },
  { label: "Pins", value: "pins" },
  { label: "Users", value: "users" },
  { label: "Boards", value: "boards" },
];

export function SearchPage() {
  const navigate = useNavigate();
  const { isAuthenticated, logout } = useAuth();
  const [searchParams] = useSearchParams();
  const query = searchParams.get("q")?.trim() ?? "";
  const target = normalizeTarget(searchParams.get("target"));
  const [searchInput, setSearchInput] = useState(query);
  const [selectedPinId, setSelectedPinId] = useState<string | null>(null);

  useEffect(() => {
    setSearchInput(query);
  }, [query]);

  const searchQuery = useQuery({
    queryKey: ["globalSearch", query, target],
    queryFn: () => searchAll(query, target),
    enabled: query.length > 0,
    staleTime: 30_000,
  });

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const nextQuery = searchInput.trim();
    if (!nextQuery) return;
    navigate(`/search?q=${encodeURIComponent(nextQuery)}&target=${target}`);
  }

  function setTarget(nextTarget: SearchTarget) {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    params.set("target", nextTarget);
    navigate(`/search?${params.toString()}`);
  }

  const results = searchQuery.data;
  const showUsers = target === "all" || target === "users";
  const showBoards = target === "all" || target === "boards";
  const showPins = target === "all" || target === "pins";

  return (
    <div>
      <header className="header">
        <Link className="header-logo" to="/" aria-label="Home">P</Link>

        <form className="header-search" onSubmit={handleSubmit}>
          <span className="header-search-icon"><Search size={18} strokeWidth={2.5} /></span>
          <input
            type="search"
            placeholder="Search"
            aria-label="Search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </form>

        <Link className="btn btn-outline" to="/">Home</Link>
        {isAuthenticated ? (
          <button className="btn btn-outline" onClick={logout}>Logout</button>
        ) : null}
        <AccountButton />
      </header>

      <main className="search-page">
        <div className="search-tabs">
          {SEARCH_TARGETS.map((item) => (
            <button
              key={item.value}
              type="button"
              className={target === item.value ? "search-tab active" : "search-tab"}
              onClick={() => setTarget(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>

        {!query ? (
          <div className="empty-state">
            <h2>Search Pinterest</h2>
            <p>Find pins, boards, and people.</p>
          </div>
        ) : searchQuery.isError ? (
          <div className="empty-state">
            <h2>Search failed</h2>
            <p>Try again in a moment.</p>
          </div>
        ) : (
          <div className="search-results">
            {showUsers && (
              <section className="search-section">
                <h2>Users</h2>
                {searchQuery.isLoading ? (
                  <div className="search-loading-row" />
                ) : results?.users.length ? (
                  <div className="user-result-grid">
                    {results.users.map((user) => (
                      <Link className="user-result" key={user.id} to={`/users/${user.username}`}>
                        <span className="header-avatar">
                          {user.avatar_url ? <img src={user.avatar_url} alt="" /> : user.username[0]}
                        </span>
                        <span>
                          <strong>{user.full_name || user.username}</strong>
                          <small>@{user.username}</small>
                        </span>
                      </Link>
                    ))}
                  </div>
                ) : (
                  <p className="search-empty-line">No users found.</p>
                )}
              </section>
            )}

            {showBoards && (
              <section className="search-section">
                <h2>Boards</h2>
                {searchQuery.isLoading ? (
                  <div className="search-loading-row" />
                ) : results?.boards.length ? (
                  <div className="board-grid search-board-grid">
                    {results.boards.map((board) => (
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
                  <p className="search-empty-line">No boards found.</p>
                )}
              </section>
            )}

            {showPins && (
              <section className="search-section search-pins-section">
                <h2>Pins</h2>
                <PinGrid
                  pins={results?.pins ?? []}
                  isLoading={searchQuery.isLoading}
                  onPinClick={(pin) => isAuthenticated ? setSelectedPinId(pin.id) : navigate("/auth")}
                />
              </section>
            )}
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
    </div>
  );
}

function normalizeTarget(value: string | null): SearchTarget {
  if (value === "users" || value === "boards" || value === "pins") return value;
  return "all";
}
