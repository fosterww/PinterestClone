import { apiClient } from "./clients";
import type { Pin, PinFilters } from "../types/api";

function serializeFilters(filters: PinFilters, offset: number, limit: number) {
    const params: Record<string, unknown> = { offset, limit };
    if (filters.search) params.search = filters.search;
    if (filters.tags?.length) params.tags = filters.tags;
    if (filters.popularity)
        params.popularity = filters.popularity.toLowerCase().replace(/ /g, "_");
    if (filters.created_at)
        params.created_at = filters.created_at.toLowerCase();
    return params;
}

export async function getPins(
    filters: PinFilters = {},
    offset: number,
    limit: number
): Promise<Pin[]> {
    const response = await apiClient.get<Pin[]>("/pins/", {
        params: serializeFilters(filters, offset, limit),
    });
    return response.data;
}

export async function createPin(data: {
    title: string;
    description?: string;
    link_url?: string;
    tags?: string[];
    image: File;
}): Promise<Pin> {
    const formData = new FormData();
    formData.append("image", data.image);
    formData.append("title", data.title);
    if (data.description) formData.append("description", data.description);
    if (data.link_url) formData.append("link_url", data.link_url);
    (data.tags ?? []).forEach(tag => formData.append("tags", tag));
    const token = localStorage.getItem("access_token");
    const response = await fetch("/api/v2/pins/", {
        method: "POST",
        headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: formData,
    });

    if (response.status === 401) {
        localStorage.removeItem("access_token");
        window.dispatchEvent(new Event("auth:logout"));
        throw new Error("Not authenticated");
    }
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error?.detail ?? `HTTP ${response.status}`);
    }

    return response.json() as Promise<Pin>;
}