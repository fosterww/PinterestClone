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
    tags: Tag[];
}

export interface PinFilters {
    search?: string;
    tags?: string[];
    popularity?: Popularity;
    created_at?: CreatedAt;
}

export interface User {
    id: string;
    username: string;
    email: string;
    bio?: string;
    avatar_url?: string;
}

export interface Board {
    id: string;
    user: User;
    title: string;
    description?: string;
    visibility: Visibility;
    pins: Pin[];
}