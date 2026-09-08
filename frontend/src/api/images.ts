// Images domain API. Mirrors backend endpoints/images.py.
//
// Co-located response types per D-04. The admin bucket-summary types are
// authoritative here and `admin.ts` imports them from this module.
import { apiClient } from './client';

export interface ImageUploadResponse {
  file_key: string;
  presigned_url: string;
  message: string;
}

export interface PresignedUrlResponse {
  presigned_url: string;
  file_key: string;
}

/** Admin-only: S3 user-images bucket totals grouped by upload key prefix (entity_type). */
export interface BucketEntityTypeCountResponse {
  total: number;
  by_entity_type: Record<string, number>;
  other: number;
  /** Total stored data in GB (sum of all object sizes). */
  size_gb?: number;
}

export const imageApi = {
  uploadImage: async (
    file: File,
    entityType: string,
    entityId?: string
  ): Promise<ImageUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    const params = new URLSearchParams();
    params.append('entity_type', entityType);
    if (entityId !== undefined) {
      params.append('entity_id', entityId.toString());
    }

    const response = await apiClient.post<ImageUploadResponse>(
      `/images/upload?${params.toString()}`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  getPresignedUrl: (
    fileKey: string,
    expiration?: number
  ): Promise<PresignedUrlResponse> => {
    const params = new URLSearchParams();
    params.append('file_key', fileKey);
    if (expiration !== undefined) {
      params.append('expiration', expiration.toString());
    }
    return apiClient
      .get<PresignedUrlResponse>(`/images/presigned-url?${params.toString()}`)
      .then((response) => response.data);
  },

  deleteImage: (
    fileKey: string
  ): Promise<{ message: string; file_key: string }> => {
    const params = new URLSearchParams();
    params.append('file_key', fileKey);
    return apiClient
      .delete<{
        message: string;
        file_key: string;
      }>(`/images/delete?${params.toString()}`)
      .then((response) => response.data);
  },

  countBucketObjects: () =>
    apiClient.get<{ count: number }>('/images/admin/count'),

  /** Single S3 pass: total plus counts by standard key prefix (admin only). */
  getBucketCountByEntityType: () =>
    apiClient.get<BucketEntityTypeCountResponse>(
      '/images/admin/count-by-entity-type'
    ),

  /** Dry run: list bucket object keys not referenced by any entity (admin only). */
  getOrphanedBucketObjects: () =>
    apiClient.get<{
      orphaned_keys: string[];
      count: number;
      total_bucket: number;
      total_referenced: number;
    }>('/images/admin/orphaned'),

  /** Delete bucket objects not referenced by any entity (admin only). Non-destructive. */
  purgeOrphanedBucketObjects: () =>
    apiClient.post<{ deleted: number; deleted_keys: string[] }>(
      '/images/admin/purge-orphaned'
    ),
};
