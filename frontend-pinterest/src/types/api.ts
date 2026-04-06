export type Visibility = "public" | "private";
export type Popularity = "Most Popular" | "Least Popular";
export type CreatedAt = "Newest" | "Oldest";

export interface Tag {
    id: string;
    name: string;
}

export interface Pin {
    id: string;
    owner_id: string;
    title: string;
    description?: string;
    image_url: string;
    link_url?: string;
    likes_count: number;
    tags: Tag[];
}

export interface PinDetail extends Pin {
    created_at: string;
    comments: PinComments[];
    user?: User;
}

export interface PinFilters {
    search?: string;
    tags?: string[];
    popularity?: Popularity;
    created_at?: CreatedAt;
}

export interface PinComments {
    id: string;
    comment: string;
    likes_count: number;
    created_at: string;
    user: User;
    replies: PinComments[];
}

export interface PinCommentCreate {
    comment: string;
    parent_id?: string | null;
}

export interface User {
    id: string;
    username: string;
    email: string;
    full_name?: string;
    bio?: string;
    avatar_url?: string;
}

export interface RegisterData {
    username: string;
    email: string;
    password: string;
    full_name?: string;
    bio?: string;
    avatar_url?: string;
}

export interface Board {
    id: string;
    user: User;
    title: string;
    description?: string;
    visibility: Visibility;
}

export interface BoardDetail extends Board {
    pins: Pin[];
}