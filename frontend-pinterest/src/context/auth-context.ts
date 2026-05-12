import { createContext } from "react";
import type { login, loginWithGoogle, logout, refreshToken, register } from "../api/auth";

export interface AuthContextType {
  isAuthenticated: boolean;
  login: typeof login;
  loginWithGoogle: typeof loginWithGoogle;
  register: typeof register;
  logout: typeof logout;
  refreshToken: typeof refreshToken;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);
