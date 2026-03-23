import { apiClient } from './clients';
import type { User } from '../types/api';

export async function login(username: string, password: string): Promise<string> {
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);

    const response = await apiClient.post("/auth/login", formData, {
        headers: {
            "Content-Type": "application/x-www-form-urlencoded"
        }
    });

    const token = response.data.access_token;
    localStorage.setItem("access_token", token);
    return token;
}

export async function register(userData: User): Promise<User> {
    const response = await apiClient.post("/auth/register", userData);
    return response.data;
}

export async function logout(): Promise<void> {
    await apiClient.post("/auth/logout", {}, {
        headers: {
            "Authorization": `Bearer ${localStorage.getItem("access_token")}`
        }
    });
    localStorage.removeItem("access_token");
}