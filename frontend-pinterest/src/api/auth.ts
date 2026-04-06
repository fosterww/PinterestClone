import { apiClient } from './clients';
import type { User, RegisterData } from '../types/api';

export async function login(username: string, password: string): Promise<string> {
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);

    const response = await apiClient.post("/auth/login", formData, {
        headers: {
            "Content-Type": "application/x-www-form-urlencoded"
        }
    });

    const { access_token, refresh_token } = response.data;
    localStorage.setItem("access_token", access_token);
    if (refresh_token) {
        localStorage.setItem("refresh_token", refresh_token);
    }
    return access_token;
}

export async function loginWithGoogle(idToken: string): Promise<string> {
    const response = await apiClient.post("/auth/google", { id_token: idToken });
    const { access_token, refresh_token } = response.data;
    localStorage.setItem("access_token", access_token);
    if (refresh_token) {
        localStorage.setItem("refresh_token", refresh_token);
    }
    return access_token;
}

export async function register(userData: RegisterData): Promise<User> {
    const response = await apiClient.post("/auth/register", userData);
    return response.data;
}

export async function refreshToken(): Promise<string> {
    const token = localStorage.getItem("refresh_token");
    if (!token) throw new Error("No refresh token available");

    const response = await apiClient.post("/auth/refresh", { refresh_token: token });
    const { access_token, refresh_token: new_refresh } = response.data;
    localStorage.setItem("access_token", access_token);
    if (new_refresh) {
        localStorage.setItem("refresh_token", new_refresh);
    }
    return access_token;
}

export async function logout(): Promise<void> {
    await apiClient.post("/auth/logout", {}, {
        headers: {
            "Authorization": `Bearer ${localStorage.getItem("access_token")}`
        }
    });
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
}