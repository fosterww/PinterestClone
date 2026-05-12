import { apiClient } from "./clients";
import type { Board, Pin, PublicUserResponse, UserResponse } from "../types/api";

export interface UserUpdate {
    full_name?: string | null;
    bio?: string | null;
    avatar_url?: string | null;
    email_notifications_enabled?: boolean;
}

export async function getCurrentUser(): Promise<UserResponse> {
    const response = await apiClient.get<UserResponse>("/users/");
    return response.data;
}

export async function updateCurrentUser(data: UserUpdate): Promise<UserResponse> {
    const response = await apiClient.patch<UserResponse>("/users/", data);
    return response.data;
}

export async function getPublicUser(username: string): Promise<PublicUserResponse> {
    const response = await apiClient.get<PublicUserResponse>(`/users/${username}`);
    return response.data;
}

export async function getUserBoards(username: string): Promise<Board[]> {
    const response = await apiClient.get<Board[]>(`/users/${username}/boards`);
    return response.data;
}

export async function getUserPins(username: string): Promise<Pin[]> {
    const response = await apiClient.get<Pin[]>(`/pins/user/${username}`);
    return response.data;
}
