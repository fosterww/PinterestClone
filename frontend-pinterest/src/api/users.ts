import { apiClient } from "./clients";
import type { User } from "../types/api";

export interface UserUpdate {
    full_name?: string;
    bio?: string;
    avatar_url?: string;
}

export async function getCurrentUser(): Promise<User> {
    const response = await apiClient.get<User>("/users/");
    return response.data;
}

export async function updateCurrentUser(data: UserUpdate): Promise<User> {
    const response = await apiClient.patch<User>("/users/", data);
    return response.data;
}
