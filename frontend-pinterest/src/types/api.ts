export type Visibility = "public" | "secret";
export type Popularity = "Most Popular" | "Least Popular";
export type CreatedAt = "Newest" | "Oldest";
export type PinProcessingState = "uploaded" | "tagged" | "indexed" | "failed";
export type PinModerationStatus = "pending" | "approved" | "hidden" | "failed";

export interface Tag {
    id: string;
    name: string;
}

export interface Pin {
    id: string;
    owner_id: string;
    user: UserSummary;
    title: string;
    description?: string;
    image_url: string;
    link_url?: string;
    created_at: string;
    likes_count: number;
    tags: Tag[];
    processing_state?: PinProcessingState;
    moderation_status?: PinModerationStatus;
    image_width?: number | null;
    image_height?: number | null;
    dominant_colors?: string[] | null;
    last_processing_error?: string | null;
    tagged_at?: string | null;
    indexed_at?: string | null;
    is_duplicate?: boolean;
    duplicate_of_pin_id?: string | null;
}

export interface PinDetail extends Pin {
    comments: PinComments[];
}

export interface PinFilters {
    search?: string;
    tags?: string[];
    popularity?: Popularity;
    created_at?: CreatedAt;
}

export type SearchTarget = "all" | "users" | "boards" | "pins";

export interface PinComments {
    id: string;
    comment: string;
    likes_count: number;
    created_at: string;
    user: UserSummary;
    replies: PinComments[];
}

export interface UserSummary {
    id: string;
    username: string;
    full_name?: string | null;
    avatar_url?: string | null;
}

export interface PinCommentCreate {
    comment: string;
    parent_id?: string | null;
}

export interface UserResponse {
    id: string;
    username: string;
    email: string;
    full_name?: string | null;
    bio?: string | null;
    avatar_url?: string | null;
    followers_count: number;
    following_count: number;
    email_notifications_enabled: boolean;
}

export interface PublicUserResponse {
    id: string;
    username: string;
    full_name?: string | null;
    bio?: string | null;
    avatar_url?: string | null;
    created_at: string;
    boards_count: number;
    pins_count: number;
}

export interface RegisterData {
    username: string;
    email: string;
    password: string;
    full_name?: string;
    bio?: string;
    avatar_url?: string;
}

export interface AuthTokenResponse {
    access_token: string;
    refresh_token?: string;
    token_type: string;
    session_id?: string;
}

export interface Board {
    id: string;
    user: UserResponse;
    title: string;
    description?: string;
    visibility: Visibility;
}

export interface BoardDetail extends Board {
    pins: Pin[];
}

export interface BoardSearchResult {
    id: string;
    title: string;
    description?: string | null;
    visibility: Visibility;
    created_at: string;
    owner_username: string;
}

export interface SearchResponse {
    query: string;
    target: SearchTarget;
    users: UserSummary[];
    boards: BoardSearchResult[];
    pins: Pin[];
}

export interface GenerateImageRequest {
    prompt: string;
    negative_prompt?: string | null;
    style?: string | null;
    aspect_ratio?: "1:1" | "16:9" | "9:16" | null;
    seed?: number | null;
    num_images?: 1;
}

export interface GeneratedImage {
    id: string;
    image_url: string;
    prompt: string;
    style?: string | null;
    expires_at: string;
}

export interface GenerateImageResponse {
    generated_images: GeneratedImage[];
    operation_id?: string | null;
}

export interface AIOperation {
    id: string;
    status: "pending" | "in_progress" | "completed" | "failed";
    error?: string | null;
    latency_ms?: number | null;
    output_id?: string | null;
}
