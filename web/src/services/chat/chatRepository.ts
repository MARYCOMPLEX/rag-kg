import type { ChatQuestionRequest, ChatQuestionResponse, ChatSession } from '../../domain/chat/types'
import { evidence, initialMessages } from '../../mocks/chat'
import { apiRequest } from '../api/httpClient'

export interface ChatRepository {
  getSession(libraryId: string): Promise<ChatSession>
  createQuestion(libraryId: string, request: ChatQuestionRequest): Promise<ChatQuestionResponse>
}

class MockChatRepository implements ChatRepository {
  async getSession(_libraryId: string) {
    return {
      sessionId: 'mock-chat-session',
      title: 'How does GraphRAG combine community summarization and vector retrieval?',
      createdAtLabel: '2026-05-05 14:32',
      messages: structuredClone(initialMessages),
      evidence: structuredClone(evidence),
    }
  }

  async createQuestion(_libraryId: string, request: ChatQuestionRequest): Promise<ChatQuestionResponse> {
    const now = Date.now()
    return {
      taskId: `mock-chat-${now}`,
      streamUrl: '',
      userMessage: {
        id: `u-${now}`,
        role: 'user',
        text: request.question,
      },
      assistantMessage: {
        id: `a-${now}`,
        role: 'assistant',
        text: '',
        status: 'streaming',
        citations: [],
      },
      evidence: [],
    }
  }
}

class HttpChatRepository implements ChatRepository {
  getSession(libraryId: string) {
    return apiRequest<ChatSession>(`/api/libraries/${encodeURIComponent(libraryId)}/chat/session`)
  }

  createQuestion(libraryId: string, request: ChatQuestionRequest) {
    return apiRequest<ChatQuestionResponse>(
      `/api/libraries/${encodeURIComponent(libraryId)}/chat/questions`,
      {
        method: 'POST',
        body: JSON.stringify(request),
      },
    )
  }
}

export function createChatRepository(): ChatRepository {
  return import.meta.env.VITE_DATA_SOURCE === 'api'
    ? new HttpChatRepository()
    : new MockChatRepository()
}
