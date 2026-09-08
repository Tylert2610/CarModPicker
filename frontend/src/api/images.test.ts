// Phase 8 plan 08-02: imageApi coverage tests.
//
// Covers every method on `imageApi` (7 total) including the FormData-based
// `uploadImage` path (POST /images/upload?entity_type=X&entity_id=Y with
// a multipart/form-data header). See PATTERNS.md §7 for the canonical Wave 1
// scaffold.
//
// apiClient is auto-mocked by setup.ts (Phase 8 D-18). Narrow the HTTP verbs
// at module scope via MockedFunction cast.
import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type MockedFunction,
} from 'vitest';
import { apiClient } from './client';
import { imageApi } from './images';

const getMock = apiClient.get as MockedFunction<typeof apiClient.get>;

const postMock = apiClient.post as MockedFunction<typeof apiClient.post>;

const deleteMock = apiClient.delete as MockedFunction<typeof apiClient.delete>;

describe('imageApi — uploadImage (FormData)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uploadImage POSTs FormData to /images/upload with entity query params and multipart header', async () => {
    const file = new File(['img-bytes'], 'test.jpg', { type: 'image/jpeg' });
    postMock.mockResolvedValueOnce({
      data: {
        file_key: 'uploads/part/test.jpg',
        presigned_url: 'https://s3.example/test.jpg',
        message: 'ok',
      },
    });

    const result = await imageApi.uploadImage(file, 'part', 'abc-123');

    expect(postMock).toHaveBeenCalledWith(
      '/images/upload?entity_type=part&entity_id=abc-123',
      expect.any(FormData),
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );

    // Inspect FormData contents — confirms file is appended under key 'file'.
    const fd = postMock.mock.calls[0]?.[1] as FormData;
    expect(fd).toBeInstanceOf(FormData);
    expect(fd.get('file')).toBe(file);

    // Method unwraps to response.data directly (not the full AxiosResponse).
    expect(result.file_key).toBe('uploads/part/test.jpg');
  });

  it('uploadImage omits entity_id param when not provided', async () => {
    const file = new File(['x'], 'a.png', { type: 'image/png' });
    postMock.mockResolvedValueOnce({
      data: { file_key: 'k', presigned_url: 'u', message: 'ok' },
    });

    await imageApi.uploadImage(file, 'user');

    expect(postMock).toHaveBeenCalledWith(
      '/images/upload?entity_type=user',
      expect.any(FormData),
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
  });
});

describe('imageApi — presigned URLs and deletion', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getPresignedUrl GETs /images/presigned-url with file_key query param', async () => {
    getMock.mockResolvedValueOnce({
      data: { presigned_url: 'https://s3/x', file_key: 'uploads/k.jpg' },
    });

    const result = await imageApi.getPresignedUrl('uploads/k.jpg');

    expect(getMock).toHaveBeenCalledWith(
      '/images/presigned-url?file_key=uploads%2Fk.jpg'
    );
    expect(result.file_key).toBe('uploads/k.jpg');
  });

  it('getPresignedUrl includes expiration query param when provided', async () => {
    getMock.mockResolvedValueOnce({
      data: { presigned_url: 'u', file_key: 'k' },
    });

    await imageApi.getPresignedUrl('k', 3600);

    expect(getMock).toHaveBeenCalledWith(
      '/images/presigned-url?file_key=k&expiration=3600'
    );
  });

  it('deleteImage DELETEs /images/delete with file_key query param', async () => {
    deleteMock.mockResolvedValueOnce({
      data: { message: 'deleted', file_key: 'k' },
    });

    const result = await imageApi.deleteImage('uploads/k.jpg');

    expect(deleteMock).toHaveBeenCalledWith(
      '/images/delete?file_key=uploads%2Fk.jpg'
    );
    expect(result.message).toBe('deleted');
  });
});

describe('imageApi — admin bucket stats', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('countBucketObjects GETs /images/admin/count', async () => {
    getMock.mockResolvedValueOnce({ data: { count: 100 } });

    const result = await imageApi.countBucketObjects();

    expect(getMock).toHaveBeenCalledWith('/images/admin/count');
    expect(result.data.count).toBe(100);
  });

  it('getBucketCountByEntityType GETs /images/admin/count-by-entity-type', async () => {
    getMock.mockResolvedValueOnce({
      data: {
        total: 1000,
        by_entity_type: { part: 500, build_list: 400, user: 100 },
        other: 0,
        size_gb: 1.5,
      },
    });

    const result = await imageApi.getBucketCountByEntityType();

    expect(getMock).toHaveBeenCalledWith('/images/admin/count-by-entity-type');
    expect(result.data.by_entity_type['part']).toBe(500);
  });

  it('getOrphanedBucketObjects GETs /images/admin/orphaned', async () => {
    getMock.mockResolvedValueOnce({
      data: {
        orphaned_keys: ['k1', 'k2'],
        count: 2,
        total_bucket: 100,
        total_referenced: 98,
      },
    });

    const result = await imageApi.getOrphanedBucketObjects();

    expect(getMock).toHaveBeenCalledWith('/images/admin/orphaned');
    expect(result.data.count).toBe(2);
  });

  it('purgeOrphanedBucketObjects POSTs /images/admin/purge-orphaned', async () => {
    postMock.mockResolvedValueOnce({
      data: { deleted: 2, deleted_keys: ['k1', 'k2'] },
    });

    const result = await imageApi.purgeOrphanedBucketObjects();

    expect(postMock).toHaveBeenCalledWith('/images/admin/purge-orphaned');
    expect(result.data.deleted).toBe(2);
  });
});
