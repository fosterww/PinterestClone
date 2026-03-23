export type Visibility = "public" | "private";

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