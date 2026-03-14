import { apiClient } from '@/lib/api-client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export interface ChatSource {
  id: string;
  type: string;
  source: string;
  score: number;
  preview: string;
}

export interface ChatMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
  created_at?: string;
  documents?: string[];
  file_links?: string[];
}

export interface ChatResponse {
  session_id: string;
  answer: string;
  sources: ChatSource[];
  documents: string[];
  file_links: string[];
}

export interface SendMessagePayload {
  message: string;
  session_id?: string | null;
}

export const useChatHistory = (sessionId: string | null | undefined, limit = 50) => {
  return useQuery({
    queryKey: ['chat-history', sessionId, limit],
        queryFn: async (): Promise<ChatMessage[]> => {
      if (sessionId === null) {
        const { data } = await apiClient.get('/v1/chat/history', { params: { limit } });
        return data;
      }
      if (!sessionId) return [];
      const { data } = await apiClient.get(`/v1/chat/${sessionId}/history`, {   
        params: { limit },
      });
      return data;
    },
    enabled: sessionId === null || !!sessionId,
  });
};

export const useSendMessage = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: SendMessagePayload): Promise<ChatResponse> => {
      const { data } = await apiClient.post('/v1/chat/message', payload);
      return data;
    },
    onSuccess: (data) => {
      // Invalidate chat history to trigger refresh
      const sessionId = data.session_id;
      if (sessionId) {
        queryClient.invalidateQueries({ queryKey: ['chat-history', sessionId] });
      }
    },
  });
};
