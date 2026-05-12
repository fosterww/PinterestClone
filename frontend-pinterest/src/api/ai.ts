import { apiClient } from "./clients";
import type {
    AIOperation,
    GenerateImageRequest,
    GenerateImageResponse,
} from "../types/api";

export async function generateImage(
    data: GenerateImageRequest
): Promise<GenerateImageResponse> {
    const response = await apiClient.post<GenerateImageResponse>(
        "/ai/generate-image",
        data
    );
    return response.data;
}

export async function getAIOperation(operationId: string): Promise<AIOperation> {
    const response = await apiClient.get<AIOperation>(`/ai/operations/${operationId}`);
    return response.data;
}
