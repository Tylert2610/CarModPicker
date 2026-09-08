import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import BuildListItem from '../components/buildLists/BuildListItem';
import PageHeader from '../components/layout/PageHeader';
import SectionHeader from '../components/layout/SectionHeader';
import SocialLinks from '../components/profile/SocialLinks';
import { ErrorAlert } from '../components/ui/alert';
import { Card } from '../components/ui/card';
import CardInfoItem from '../components/ui/card-info-item';
import Spinner from '../components/ui/spinner';
import useApiRequest from '../hooks/UseApiRequest';
import { useDocumentMeta } from '../hooks/useDocumentMeta';
import { buildListsApi } from '../api/build_lists';
import { apiClient } from '../api/client';
import type { BuildListRead, UserRead } from '../types/Api';

const fetchUserRequestFn = (
  userId: string // userId will be a string from URL params
) => apiClient.get<UserRead>(`/users/${userId}`);

const fetchBuildListsByUserRequestFn = (userId: string) =>
  buildListsApi.getBuildListsByUser(userId);

function ViewUser() {
  const { userId: userIdParam } = useParams<{ userId: string }>();

  const {
    data: user,
    isLoading: isLoadingUser,
    error: userApiError,
    executeRequest: fetchUser,
  } = useApiRequest(fetchUserRequestFn);

  const {
    data: buildListsResponse,
    isLoading: isLoadingBuildLists,
    executeRequest: fetchBuildListsByUser,
  } = useApiRequest(fetchBuildListsByUserRequestFn);

  useEffect(() => {
    if (userIdParam) {
      void fetchUser(userIdParam);
    }
  }, [userIdParam, fetchUser]);

  useEffect(() => {
    if (user?.id != null) {
      void fetchBuildListsByUser(user.id);
    }
  }, [user?.id, fetchBuildListsByUser]);

  const buildLists: BuildListRead[] = buildListsResponse ?? [];

  useDocumentMeta({
    title: user?.username ? `${user.username}'s Profile` : 'User Profile',
    description: user?.username
      ? `View ${user.username}'s car builds, parts, and activity on CarModPicker.`
      : 'View a member profile on CarModPicker.',
    canonicalPath: userIdParam ? `/user/${userIdParam}` : undefined,
  });

  if (isLoadingUser) {
    return (
      <>
        <PageHeader title="User Profile" />
        <Spinner />
      </>
    );
  }

  if (userApiError) {
    return (
      <div>
        <PageHeader title="User Profile" />
        <Card>
          <ErrorAlert
            message={`Failed to load profile for User ID "${userIdParam}". ${userApiError}`}
          />
        </Card>
      </div>
    );
  }

  if (!user || user.is_service_account) {
    return (
      <div>
        <PageHeader title="User Profile" />
        <Card>
          <ErrorAlert message={`User with ID "${userIdParam}" not found.`} />
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader title={`Profile: ${user.username}`} />
      <Card>
        <SectionHeader title="Public Profile Information" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <CardInfoItem label="Profile Picture">
            {user.image_urls?.[0] ? (
              <img
                src={user.image_urls[0]}
                alt={`${user.username}'s profile`}
                className="h-48 w-48 rounded-lg object-cover"
              />
            ) : (
              <p className="text-muted-foreground">No image set.</p>
            )}
          </CardInfoItem>
          <CardInfoItem label="Username" className="md:col-start-1">
            <p>{user.username}</p>
          </CardInfoItem>
        </div>
        <SocialLinks
          links={{
            instagram_url: user.instagram_url ?? null,
            facebook_url: user.facebook_url ?? null,
            reddit_url: user.reddit_url ?? null,
            youtube_url: user.youtube_url ?? null,
            tiktok_url: user.tiktok_url ?? null,
          }}
          className="mt-4 pt-4 border-t border-gray-700"
        />
      </Card>

      <div className="mt-8">
        <SectionHeader title={`${user.username}'s Build Lists`} />
        {isLoadingBuildLists ? (
          <Spinner />
        ) : buildLists.length > 0 ? (
          <div className="tile-grid-compact mt-4">
            {buildLists.map((buildList) => (
              <BuildListItem key={buildList.id} buildList={buildList} />
            ))}
          </div>
        ) : (
          <p className="text-muted-foreground mt-4">
            This user has no public build lists yet.
          </p>
        )}
      </div>
    </div>
  );
}

export default ViewUser;
