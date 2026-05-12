import { apiClient } from "./clients";
import type { SearchResponse, SearchTarget } from "../types/api";

export async function searchAll(
    query: string,
    target: SearchTarget = "all",
    offset = 0,
    limit = 20
): Promise<SearchResponse> {
    const response = await apiClient.get<SearchResponse>("/search/", {
        params: {
            q: query,
            target,
            offset,
            limit,
        },
    });
    return response.data;
}
