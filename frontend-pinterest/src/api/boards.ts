import { apiClient } from "./clients";
import type { Board, BoardDetail } from "../types/api";

export interface BoardCreate {
    title: string;
    description?: string;
    visibility?: "public" | "private";
}

export interface BoardUpdate {
    title?: string;
    description?: string;
    visibility?: "public" | "private";
}

export async function getBoards(): Promise<Board[]> {
    const response = await apiClient.get<Board[]>("/boards/");
    return response.data;
}

export async function getBoardById(boardId: string): Promise<BoardDetail> {
    const response = await apiClient.get<BoardDetail>(`/boards/${boardId}`);
    return response.data;
}

export async function createBoard(data: BoardCreate): Promise<Board> {
    const response = await apiClient.post<Board>("/boards/", data);
    return response.data;
}

export async function updateBoard(boardId: string, data: BoardUpdate): Promise<Board> {
    const response = await apiClient.patch<Board>(`/boards/${boardId}`, data);
    return response.data;
}

export async function addPinToBoard(boardId: string, pinId: string): Promise<void> {
    await apiClient.post(`/boards/${boardId}/pins/${pinId}`);
}

export async function removePinFromBoard(boardId: string, pinId: string): Promise<void> {
    await apiClient.delete(`/boards/${boardId}/pins/${pinId}`);
}
