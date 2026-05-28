import type {
  ReviewCancelRequest,
  ReviewCancelResponse,
  ReviewCreateRequest,
  ReviewRegenerateRequest,
  ReviewSnapshot,
} from '../../domain/review/types'
import { reviewSnapshot } from '../../mocks/review'
import { apiRequest } from '../api/httpClient'

export interface ReviewRepository {
  getCurrent(libraryId: string): Promise<ReviewSnapshot>
  createReview(libraryId: string, request: ReviewCreateRequest): Promise<ReviewSnapshot>
  regenerateSection(
    libraryId: string,
    reviewRunId: string,
    sectionId: string,
    request: ReviewRegenerateRequest,
  ): Promise<ReviewSnapshot>
  cancelReview(libraryId: string, reviewRunId: string, request: ReviewCancelRequest): Promise<ReviewCancelResponse>
}

class MockReviewRepository implements ReviewRepository {
  async getCurrent(_libraryId: string) {
    return structuredClone(reviewSnapshot)
  }

  async createReview(_libraryId: string, _request: ReviewCreateRequest) {
    return structuredClone(reviewSnapshot)
  }

  async regenerateSection(_libraryId: string, _reviewRunId: string, _sectionId: string, _request: ReviewRegenerateRequest) {
    return structuredClone(reviewSnapshot)
  }

  async cancelReview(_libraryId: string, _reviewRunId: string, _request: ReviewCancelRequest): Promise<ReviewCancelResponse> {
    return {
      tone: 'warning',
      title: 'Review cancelled',
      detail: 'Mock review generation paused.',
      action: 'Resume',
      run: structuredClone(reviewSnapshot.run),
    }
  }
}

class HttpReviewRepository implements ReviewRepository {
  getCurrent(libraryId: string) {
    return apiRequest<ReviewSnapshot>(`/api/libraries/${encodeURIComponent(libraryId)}/reviews/current`)
  }

  createReview(libraryId: string, request: ReviewCreateRequest) {
    return apiRequest<ReviewSnapshot>(
      `/api/libraries/${encodeURIComponent(libraryId)}/reviews`,
      {
        method: 'POST',
        body: JSON.stringify(request),
      },
    )
  }

  regenerateSection(libraryId: string, reviewRunId: string, sectionId: string, request: ReviewRegenerateRequest) {
    return apiRequest<ReviewSnapshot>(
      `/api/libraries/${encodeURIComponent(libraryId)}/reviews/${encodeURIComponent(reviewRunId)}/sections/${encodeURIComponent(sectionId)}:regenerate`,
      {
        method: 'POST',
        body: JSON.stringify(request),
      },
    )
  }

  cancelReview(libraryId: string, reviewRunId: string, request: ReviewCancelRequest) {
    return apiRequest<ReviewCancelResponse>(
      `/api/libraries/${encodeURIComponent(libraryId)}/reviews/${encodeURIComponent(reviewRunId)}:cancel`,
      {
        method: 'POST',
        body: JSON.stringify(request),
      },
    )
  }
}

export function createReviewRepository(): ReviewRepository {
  return import.meta.env.VITE_DATA_SOURCE === 'api'
    ? new HttpReviewRepository()
    : new MockReviewRepository()
}
