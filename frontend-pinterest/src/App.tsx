import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getPins, createPin } from './api/pins'
import { PinGrid } from './components/PinGrid'
import { useAuth } from './context/AuthContext'
import { LoginForm } from './components/LoginForm'
import { CreatePinModal } from './components/CreatePinModal'
import { SearchFilters } from './components/SearchFilters'
import type { PinFilters } from './types/api'

function SearchIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.35-4.35" />
    </svg>
  );
}

function App() {
  const { isAuthenticated, logout } = useAuth();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [filters, setFilters] = useState<PinFilters>({});

  const { data: pins, isLoading, isError } = useQuery({
    queryKey: ["pins", filters],
    queryFn: () => getPins(filters, 0, 100),
    enabled: isAuthenticated,
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: createPin,
    onSuccess: () => {
      // Throw away cached pins → PinGrid will auto-refresh with the new pin
      queryClient.invalidateQueries({ queryKey: ["pins"] });
      setShowCreate(false);
    },
  });

  if (!isAuthenticated) return <LoginForm />;

  const mutationError = createMutation.error
    ? (createMutation.error as any)?.response?.data?.detail ?? "Failed to create pin"
    : null;

  return (
    <div>
      <header className="header">
        <a className="header-logo" href="/" aria-label="Home">P</a>

        <div className="header-search">
          <span className="header-search-icon"><SearchIcon /></span>
          <input
            type="search"
            placeholder="Search"
            aria-label="Search"
            value={filters.search ?? ""}
            onChange={(e) =>
              setFilters((prev) => ({ ...prev, search: e.target.value || undefined }))
            }
          />
        </div>

        <SearchFilters filters={filters} onChange={setFilters} />

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
      </header>

      {isError ? (
        <div className="empty-state">
          <div style={{ fontSize: 48 }}>⚠️</div>
          <h2>Couldn't load pins</h2>
          <p>Check that your backend is running at port 8000.</p>
        </div>
      ) : (
        <PinGrid pins={pins ?? []} isLoading={isLoading} />
      )}

      <CreatePinModal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        onSubmit={(data) => createMutation.mutate(data)}
        isPending={createMutation.isPending}
        error={typeof mutationError === "string" ? mutationError : null}
      />
    </div>
  );
}

export default App;
