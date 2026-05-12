import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import { getPins, createPin, getPersonalizedPins } from './api/pins'
import { getApiErrorMessage } from './api/clients'
import { PinGrid } from './components/PinGrid'
import { useAuth } from './context/useAuth'
import { LoginForm } from './components/LoginForm'
import { CreatePinModal } from './components/CreatePinModal'
import { SearchFilters } from './components/SearchFilters'
import { PinDetailModal } from './components/PinDetailModal'
import { AccountButton } from './components/AccountButton'
import { BoardPage } from './pages/BoardPage'
import { UserPage } from './pages/UserPage'
import { SearchPage } from './pages/SearchPage'
import type { PinFilters } from './types/api'

type FeedMode = "all" | "personalized";

function HomePage() {
  const { isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [filters, setFilters] = useState<PinFilters>({});
  const [feedMode, setFeedMode] = useState<FeedMode>("all");
  const [searchInput, setSearchInput] = useState("");
  const [selectedPinId, setSelectedPinId] = useState<string | null>(null);

  const { data: pins, isLoading, isError } = useQuery({
    queryKey: ["pins", feedMode, filters, isAuthenticated],
    queryFn: () => feedMode === "personalized" && isAuthenticated
      ? getPersonalizedPins()
      : getPins(filters, 0, 100),
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!isAuthenticated && feedMode === "personalized") {
      setFeedMode("all");
    }
  }, [feedMode, isAuthenticated]);

  const createMutation = useMutation({
    mutationFn: createPin,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pins"] });
      setShowCreate(false);
    },
  });

  const mutationError = createMutation.error
    ? getApiErrorMessage(createMutation.error, "Failed to create pin")
    : null;

  function handleSearchSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const query = searchInput.trim();
    if (!query) return;
    navigate(`/search?q=${encodeURIComponent(query)}&target=all`);
  }

  return (
    <div>
      <header className="header">
        <Link className="header-logo" to="/" aria-label="Home">P</Link>

        <form className="header-search" onSubmit={handleSearchSubmit}>
          <span className="header-search-icon"><Search size={18} strokeWidth={2.5} /></span>
          <input
            type="search"
            placeholder="Search"
            aria-label="Search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </form>

        {isAuthenticated && (
          <div className="feed-switch" aria-label="Feed">
            <button
              type="button"
              className={feedMode === "all" ? "feed-switch-btn active" : "feed-switch-btn"}
              onClick={() => setFeedMode("all")}
            >
              All
            </button>
            <button
              type="button"
              className={feedMode === "personalized" ? "feed-switch-btn active" : "feed-switch-btn"}
              onClick={() => setFeedMode("personalized")}
            >
              For you
            </button>
          </div>
        )}

        {feedMode === "all" && <SearchFilters filters={filters} onChange={setFilters} />}

        {isAuthenticated ? (
          <>
            <button
              className="btn btn-red"
              style={{ flexShrink: 0, height: 40, padding: "0 16px" }}
              onClick={() => setShowCreate(true)}
            >
              Create
            </button>

            <button
              className="btn btn-outline"
              style={{ flexShrink: 0, height: 40, padding: "0 16px" }}
              onClick={logout}
            >
              Logout
            </button>
          </>
        ) : (
          <AccountButton />
        )}
        {isAuthenticated && <AccountButton />}
      </header>

      <div className="app-container">
        <main className="app-main">
          {isError ? (
            <div className="empty-state">
              <div style={{ fontSize: 48 }}>⚠️</div>
              <h2>Couldn't load pins</h2>
              <p>Check that your backend is running at port 8000.</p>
            </div>
          ) : (
            <PinGrid
              pins={pins ?? []}
              isLoading={isLoading}
              onPinClick={(p) => isAuthenticated ? setSelectedPinId(p.id) : navigate("/auth")}
            />
          )}
        </main>

        {selectedPinId && (
          <PinDetailModal
            pinId={selectedPinId}
            onClose={() => setSelectedPinId(null)}
            onPinSelect={(id: string) => setSelectedPinId(id)}
          />
        )}
      </div>

      {isAuthenticated && (
        <CreatePinModal
          isOpen={showCreate}
          onClose={() => setShowCreate(false)}
          onSubmit={(data) => createMutation.mutate(data)}
          isPending={createMutation.isPending}
          error={typeof mutationError === "string" ? mutationError : null}
        />
      )}
    </div>
  );
}

function AuthPage() {
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) return <Navigate to="/" replace />;

  return <LoginForm />;
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/auth" element={<AuthPage />} />
      <Route path="/search" element={<SearchPage />} />
      <Route path="/users/:username" element={<UserPage />} />
      <Route path="/boards/:boardId" element={<BoardPage />} />
    </Routes>
  );
}

export default App;
