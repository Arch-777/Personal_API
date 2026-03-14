import { apiClient } from '@/lib/api-client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export interface Connector {
  id?: string;
  platform: string;
  platform_email?: string;
  status: string;
  last_synced?: string;
  error_message?: string;
}

export const useConnectors = () => {
  return useQuery({
    queryKey: ['connectors'],
    queryFn: async () => {
      try {
        const { data } = await apiClient.get('/v1/connectors/');
        return data as Connector[];
      } catch (error) {
        console.error("Error fetching connectors, falling back to mock", error);
        return [] as Connector[];
      }
    }
  });
};

export const useGetConnectUrl = () => {
  return useMutation({
    mutationFn: async (platform: string) => {
      let url = `/v1/connectors/${platform}/connect`;
      if (['gmail', 'drive', 'gcal'].includes(platform)) {
        url = `/v1/connectors/google/connect?platform=${platform}`;
      }
      const { data } = await apiClient.get(url);
      return data.url;
    }
  });
};

export const useSyncConnector = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (platform: string) => {
      const { data } = await apiClient.post(`/v1/connectors/${platform}/sync`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
    }
  });
};

