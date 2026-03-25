import axios from 'axios';

export const apiClient = axios.create({
    baseURL: '/api/v2',
    headers: {
        'Content-Type': 'application/json',
    },
})


apiClient.interceptors.request.use((config) => {
    const token = localStorage.getItem("access_token");
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem("access_token");
            window.dispatchEvent(new Event("auth:logout"));
        }
        return Promise.reject(error);
    }
);