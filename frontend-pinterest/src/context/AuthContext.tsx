import { createContext, useContext, useState, useEffect } from "react";
import type { ReactNode } from "react";
import { jwtDecode } from "jwt-decode";
import { login, logout, register } from "../api/auth";

interface AuthContextType {
  isAuthenticated: boolean;
  login: typeof login;
  register: typeof register;
  logout: typeof logout;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      try {
        const decoded = jwtDecode(token);
        if (decoded && decoded.exp && decoded.exp * 1000 > Date.now()) {
          setIsAuthenticated(true);
        } else {
          localStorage.removeItem("access_token");
          setIsAuthenticated(false);
        }
      } catch (error) {
        setIsAuthenticated(false);
      }
    }

    const handleForcedLogout = () => setIsAuthenticated(false);
    window.addEventListener("auth:logout", handleForcedLogout);
    return () => window.removeEventListener("auth:logout", handleForcedLogout);
  }, []);

  const handleLogin = async (...args: Parameters<typeof login>) => {
    try {
      const result = await login(...args);
      setIsAuthenticated(true);
      return result;
    } catch (error) {
      setIsAuthenticated(false);
      throw error;
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error("Error logging out:", error);
    } finally {
      setIsAuthenticated(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        login: handleLogin,
        register,
        logout: handleLogout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
