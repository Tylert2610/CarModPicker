import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type MockedFunction,
} from 'vitest';
import { apiClient } from './client';
import { usersApi } from './users';
import { mockUser } from '../test/mocks/api';

const getMock = apiClient.get as MockedFunction<typeof apiClient.get>;

const postMock = apiClient.post as MockedFunction<typeof apiClient.post>;

const putMock = apiClient.put as MockedFunction<typeof apiClient.put>;

const deleteMock = apiClient.delete as MockedFunction<typeof apiClient.delete>;

describe('usersApi — CRUD', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getMe GETs /users/me', async () => {
    getMock.mockResolvedValueOnce({ data: mockUser });

    const result = await usersApi.getMe();

    expect(getMock).toHaveBeenCalledWith('/users/me');
    expect(result.data).toEqual(mockUser);
  });

  it('createUser POSTs /users/ with the UserCreate body', async () => {
    const body = {
      username: 'newuser',
      email: 'new@example.com',
      password: 'pw12345678',
    };
    postMock.mockResolvedValueOnce({ data: mockUser });

    await usersApi.createUser(body);

    expect(postMock).toHaveBeenCalledWith('/users/', body);
  });

  it('getUser GETs /users/:id', async () => {
    getMock.mockResolvedValueOnce({ data: mockUser });

    await usersApi.getUser(mockUser.id);

    expect(getMock).toHaveBeenCalledWith(`/users/${mockUser.id}`);
  });

  it('updateUser PUTs /users/:id with the UserUpdate body', async () => {
    const body = { username: 'updated' };
    putMock.mockResolvedValueOnce({
      data: { ...mockUser, username: 'updated' },
    });

    await usersApi.updateUser(mockUser.id, body);

    expect(putMock).toHaveBeenCalledWith(`/users/${mockUser.id}`, body);
  });

  it('deleteUser DELETEs /users/:id', async () => {
    deleteMock.mockResolvedValueOnce({ data: mockUser });

    await usersApi.deleteUser(mockUser.id);

    expect(deleteMock).toHaveBeenCalledWith(`/users/${mockUser.id}`);
  });
});

describe('usersApi — profile picture (FormData)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uploadProfilePicture POSTs FormData with multipart/form-data header', async () => {
    const file = new File(['avatar-bytes'], 'avatar.png', {
      type: 'image/png',
    });
    postMock.mockResolvedValueOnce({ data: mockUser });

    await usersApi.uploadProfilePicture(file);

    expect(postMock).toHaveBeenCalledWith(
      '/users/me/profile-picture',
      expect.any(FormData),
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );

    const fd = postMock.mock.calls[0]?.[1] as FormData;
    expect(fd).toBeInstanceOf(FormData);
    expect(fd.get('file')).toBe(file);
  });

  it('deleteProfilePicture DELETEs /users/me/profile-picture', async () => {
    deleteMock.mockResolvedValueOnce({ data: mockUser });

    await usersApi.deleteProfilePicture();

    expect(deleteMock).toHaveBeenCalledWith('/users/me/profile-picture');
  });
});

describe('usersApi — list + count', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('listUsers GETs /users/ with pagination params', async () => {
    getMock.mockResolvedValueOnce({ data: [mockUser] });
    const params = { skip: 0, limit: 10, search: 'test' };

    await usersApi.listUsers(params);

    expect(getMock).toHaveBeenCalledWith('/users/', { params });
  });

  it('listUsers GETs /users/ with undefined params when none provided', async () => {
    getMock.mockResolvedValueOnce({ data: [mockUser] });

    await usersApi.listUsers();

    expect(getMock).toHaveBeenCalledWith('/users/', { params: undefined });
  });

  it('countUsers GETs /users/count', async () => {
    getMock.mockResolvedValueOnce({ data: { count: 42 } });

    const result = await usersApi.countUsers();

    expect(getMock).toHaveBeenCalledWith('/users/count');
    expect(result.data.count).toBe(42);
  });
});

describe('usersApi — admin endpoints', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getAllUsers GETs /users/admin/users with params', async () => {
    getMock.mockResolvedValueOnce({
      data: {
        items: [mockUser],
        total: 1,
        skip: 0,
        limit: 10,
        has_next: false,
      },
    });
    const params = { skip: 0, limit: 10 };

    await usersApi.getAllUsers(params);

    expect(getMock).toHaveBeenCalledWith('/users/admin/users', { params });
  });

  it('adminUpdateUser PUTs /users/admin/users/:id with AdminUserUpdate body', async () => {
    const body = { is_admin: true };
    putMock.mockResolvedValueOnce({ data: { ...mockUser, is_admin: true } });

    await usersApi.adminUpdateUser(mockUser.id, body);

    expect(putMock).toHaveBeenCalledWith(
      `/users/admin/users/${mockUser.id}`,
      body
    );
  });

  it('adminDeleteUser DELETEs /users/admin/users/:id', async () => {
    deleteMock.mockResolvedValueOnce({ data: mockUser });

    await usersApi.adminDeleteUser(mockUser.id);

    expect(deleteMock).toHaveBeenCalledWith(
      `/users/admin/users/${mockUser.id}`
    );
  });
});
