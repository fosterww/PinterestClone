import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getCurrentUser } from "../api/users";
import { useAuth } from "../context/useAuth";

export function AccountButton() {
  const { isAuthenticated } = useAuth();

  const currentUserQuery = useQuery({
    queryKey: ["currentUser"],
    queryFn: getCurrentUser,
    enabled: isAuthenticated,
    staleTime: 60_000,
  });

  if (!isAuthenticated) {
    return (
      <Link
        className="btn btn-red"
        style={{ flexShrink: 0, height: 40, padding: "0 16px" }}
        to="/auth"
      >
        Log in
      </Link>
    );
  }

  const user = currentUserQuery.data;
  const username = user?.username;
  const label = user?.full_name || username || "Account";
  const initial = username?.[0]?.toUpperCase() || "U";

  return (
    <Link
      className="header-avatar account-avatar-link"
      to={username ? `/users/${username}` : "/"}
      title={label}
      aria-label="Account"
    >
      {user?.avatar_url ? <img src={user.avatar_url} alt="" /> : initial}
    </Link>
  );
}
