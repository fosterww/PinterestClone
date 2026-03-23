import { apiClient } from "./clients";
import type { Pin } from "../types/api";

export async function getPins(offset: number, limit: number): Promise<Pin[]> {
    const response = await apiClient.get<Pin[]>("/pins/list", {
        params: {
            offset,
            limit,
        },
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

    const response = await apiClient.post<Pin>("/pins/create", formData, {
        headers: { "Content-Type": undefined },
    });
    return response.data;
}