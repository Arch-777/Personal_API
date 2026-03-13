// Placeholder for auth hook
import { apiClient } from '@/lib/api-client';
import { useMutation, useQuery } from '@tanstack/react-query';

export const useUser = () => {
    return useQuery({
        queryKey: ['me'],
        queryFn: async () => {
            // Mock or real endpoint
            // const { data } = await apiClient.get('/users/me');
            // return data;
            return { id: '1', name: 'Demo User', email: 'demo@example.com' };
        },
    });
};

export const useLogin = () => {
    return useMutation({
        mutationFn: async (credentials: { email: string; password: string }) => {
            const { data } = await apiClient.post('/auth/token', credentials);
            return data;
        },
        onSuccess: (data) => {
            localStorage.setItem('access_token', data.access_token);
        }
    });
};

// Accepts the JWT credential (id_token) returned by GoogleLogin component
export const useGoogleAuth = (onSuccess?: () => void) => {
    return useMutation({
        mutationFn: async (idToken: string) => {
            const { data } = await apiClient.post('/auth/google', { id_token: idToken });
            return data;
        },
        onSuccess: (data) => {
            localStorage.setItem('access_token', data.access_token);
            onSuccess?.();
        },
    });
};
