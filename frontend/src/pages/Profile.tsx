import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import AuthCard from '../components/auth/AuthCard';
import AuthRedirectLink from '../components/auth/AuthRedirectLink';
import ImageUpload from '../components/forms/ImageUpload';
import Divider from '../components/layout/Divider';
import PageHeader from '../components/layout/PageHeader';
import SectionHeader from '../components/layout/SectionHeader';
import SecuritySettingsDialog from '../components/profile/SecuritySettingsDialog';
import { ConfirmationAlert, ErrorAlert } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import CardInfoItem from '../components/ui/card-info-item';
import { Input } from '../components/ui/input';
import Spinner from '../components/ui/spinner';
import useApiRequest from '../hooks/UseApiRequest';
import { useAuth } from '../hooks/useAuth';
import { apiClient } from '../api/client';
import type { UserRead, UserUpdate } from '../types/Api';

function Profile() {
  const navigate = useNavigate();
  const {
    user,
    isLoading: authIsLoading,
    checkAuthStatus,
    login: authLogin,
  } = useAuth();

  const [isEditing, setIsEditing] = useState(false);
  const [isSecurityDialogOpen, setIsSecurityDialogOpen] = useState(false);
  const [imageFileKey, setImageFileKey] = useState<string | null>(null);
  const [imageChanged, setImageChanged] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{
    type: 'success' | 'error' | 'info';
    message: string;
  } | null>(null);
  const [socialLinks, setSocialLinks] = useState<{
    instagram_url: string;
    facebook_url: string;
    reddit_url: string;
    youtube_url: string;
    tiktok_url: string;
  }>({
    instagram_url: '',
    facebook_url: '',
    reddit_url: '',
    youtube_url: '',
    tiktok_url: '',
  });

  useEffect(() => {
    if (user) {
      // Note: user.image_urls[0] is a presigned URL from the API
      setImageFileKey(null);
      setImageChanged(false);
      setSocialLinks({
        instagram_url: user.instagram_url ?? '',
        facebook_url: user.facebook_url ?? '',
        reddit_url: user.reddit_url ?? '',
        youtube_url: user.youtube_url ?? '',
        tiktok_url: user.tiktok_url ?? '',
      });
    }
  }, [user]);

  const updateUserRequestFn = (payload: { userId: string; data: UserUpdate }) =>
    apiClient.put<UserRead>(`/users/${payload.userId}`, payload.data);

  const {
    error: updateApiError,
    isLoading: isUpdating,
    executeRequest: executeUpdateUser,
    setError: setUpdateApiError,
  } = useApiRequest(updateUserRequestFn);

  const handleEditToggle = () => {
    setIsEditing(!isEditing);
    setUpdateApiError(null);
    setStatusMessage(null);
    if (user) {
      setImageFileKey(null);
      setImageChanged(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!user) return;
    setUpdateApiError(null);
    setStatusMessage(null);

    const payload: UserUpdate = {};
    let hasChanges = false;

    // Image - only include if changed
    if (imageChanged) {
      payload.image_urls = imageFileKey ? [imageFileKey] : null;
      hasChanges = true;
    }

    if (!hasChanges) {
      setStatusMessage({
        type: 'info',
        message:
          'No changes were detected in your profile information. ' +
          'To save, please modify the fields you wish to change.',
      });
      return;
    }

    const result = await executeUpdateUser({ userId: user.id, data: payload });

    if (result) {
      authLogin(result); // Use the returned user data to update auth context
      setIsEditing(false);
      setStatusMessage({
        type: 'success',
        message: 'Profile updated successfully!',
      });
    }
  };

  const handleSaveSocialLinks = async (
    event: React.FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault();
    if (!user) return;
    setUpdateApiError(null);
    setStatusMessage(null);

    const payload: UserUpdate = {
      instagram_url: socialLinks.instagram_url.trim() || null,
      facebook_url: socialLinks.facebook_url.trim() || null,
      reddit_url: socialLinks.reddit_url.trim() || null,
      youtube_url: socialLinks.youtube_url.trim() || null,
      tiktok_url: socialLinks.tiktok_url.trim() || null,
    };

    const result = await executeUpdateUser({ userId: user.id, data: payload });

    if (result) {
      authLogin(result);
      setStatusMessage({
        type: 'success',
        message: 'Social links updated successfully!',
      });
    }
  };

  if (authIsLoading) {
    return <Spinner />;
  }

  if (!user) {
    return (
      <AuthCard title="Profile">
        <ErrorAlert message="User not found. Please log in." />
        <AuthRedirectLink text="Go to" linkText="Login" to="/login" />
      </AuthCard>
    );
  }

  const socialFields: {
    id: string;
    label: string;
    placeholder: string;
    key: keyof typeof socialLinks;
  }[] = [
    {
      id: 'instagram_url',
      label: 'Instagram',
      placeholder: 'https://instagram.com/yourusername',
      key: 'instagram_url',
    },
    {
      id: 'facebook_url',
      label: 'Facebook',
      placeholder: 'https://facebook.com/yourpage',
      key: 'facebook_url',
    },
    {
      id: 'reddit_url',
      label: 'Reddit',
      placeholder: 'https://reddit.com/user/yourusername',
      key: 'reddit_url',
    },
    {
      id: 'youtube_url',
      label: 'YouTube',
      placeholder: 'https://youtube.com/@yourchannel',
      key: 'youtube_url',
    },
    {
      id: 'tiktok_url',
      label: 'TikTok',
      placeholder: 'https://tiktok.com/@yourusername',
      key: 'tiktok_url',
    },
  ];

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader
        title="Profile"
        subtitle={`Manage your account details, ${user.username}.`}
      />
      <Card>
        <SectionHeader title="Account Information" />

        {statusMessage && (
          <div className="mb-4">
            {statusMessage.type === 'success' && (
              <ConfirmationAlert message={statusMessage.message} />
            )}
            {statusMessage.type === 'error' && (
              <ErrorAlert message={statusMessage.message} />
            )}
            {statusMessage.type === 'info' && (
              <ConfirmationAlert message={statusMessage.message} />
            )}
          </div>
        )}
        {updateApiError && (
          <div className="mb-4">
            <ErrorAlert message={updateApiError} />
          </div>
        )}

        {!isEditing ? (
          <>
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

              <CardInfoItem label="Username:">
                <p>{user.username}</p>
              </CardInfoItem>
              <CardInfoItem label="Email:">
                <p>{user.email}</p>
              </CardInfoItem>
              <CardInfoItem label="Email Verified">
                {user.email_verified ? (
                  <ConfirmationAlert message="Yes" />
                ) : (
                  <div className="flex items-center">
                    <ErrorAlert message="No" />
                    <Link
                      to="/verify-email"
                      className="ml-2 text-sm text-info hover:text-info/90"
                    >
                      Verify Email
                    </Link>
                  </div>
                )}
              </CardInfoItem>
              <CardInfoItem label="Account Status">
                <p>{user.disabled ? 'Disabled' : 'Active'}</p>
              </CardInfoItem>
              <CardInfoItem label="Two-Factor Authentication">
                {user.totp_enabled ? (
                  <ConfirmationAlert message="Enabled" />
                ) : (
                  <ErrorAlert message="Disabled" />
                )}
              </CardInfoItem>
            </div>
            <div className="flex space-x-2">
              <Button onClick={handleEditToggle} className="mr-2">
                Edit Profile
              </Button>
              <Button
                onClick={() => setIsSecurityDialogOpen(true)}
                className="bg-info hover:bg-info/90"
              >
                Manage Security Settings
              </Button>
            </div>
          </>
        ) : (
          <form
            onSubmit={(e) => void handleSubmit(e)}
            className="space-y-6 mb-6"
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <CardInfoItem label="Username:">
                <p className="text-muted-foreground">{user.username}</p>
                <p className="text-xs text-muted-foreground/80 mt-1">
                  Username cannot be changed
                </p>
              </CardInfoItem>
              <CardInfoItem label="Email:">
                <p className="text-muted-foreground">{user.email}</p>
                <p className="text-xs text-muted-foreground/80 mt-1">
                  Email cannot be changed
                </p>
              </CardInfoItem>
            </div>
            <ImageUpload
              currentImageUrl={user.image_urls?.[0] ?? null}
              entityType="user"
              entityId={user.id}
              onImageUploaded={(fileKey) => {
                setImageFileKey(fileKey);
                setImageChanged(true);
              }}
              onImageRemoved={() => {
                setImageFileKey(null);
                setImageChanged(true);
              }}
              label="Profile Image (Optional)"
              maxSizeMB={10}
            />
            <div className="flex space-x-2 pt-2">
              <Button
                type="submit"
                disabled={isUpdating}
                loading={isUpdating}
                className="w-full"
              >
                {isUpdating ? 'Saving...' : 'Save Changes'}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={handleEditToggle}
                disabled={isUpdating}
                className="w-full"
              >
                Cancel
              </Button>
            </div>
          </form>
        )}

        <Divider />
        <Button
          onClick={() =>
            void (async () => {
              setStatusMessage(null);
              setUpdateApiError(null);
              await checkAuthStatus();
              setStatusMessage({
                type: 'success',
                message: 'Profile data refreshed.',
              });
            })()
          }
          disabled={authIsLoading || isUpdating}
        >
          {authIsLoading || isUpdating
            ? 'Refreshing...'
            : 'Refresh Profile Data'}
        </Button>

        <div className="mt-4 space-y-2">
          <Button onClick={() => void navigate('/my-parts')} className="w-full">
            Manage My Parts
          </Button>
        </div>
      </Card>

      <Card className="mt-8">
        <SectionHeader title="Social Links" />
        <p className="text-muted-foreground text-sm mb-4">
          Add links to your social profiles. They will be shown on your public
          profile. Leave blank to hide.
        </p>
        <form
          onSubmit={(e) => void handleSaveSocialLinks(e)}
          className="space-y-4"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {socialFields.map((field) => (
              <div key={field.id}>
                <label
                  htmlFor={field.id}
                  className="block text-sm font-medium text-foreground mb-2"
                >
                  {field.label}
                </label>
                <Input
                  type="url"
                  placeholder={field.placeholder}
                  value={socialLinks[field.key]}
                  onChange={(e) =>
                    setSocialLinks((prev) => ({
                      ...prev,
                      [field.key]: e.target.value,
                    }))
                  }
                  id={field.id}
                  name={field.id}
                />
              </div>
            ))}
          </div>
          <div className="pt-2">
            <Button
              type="submit"
              disabled={isUpdating}
              loading={isUpdating}
              className="w-full"
            >
              {isUpdating ? 'Saving...' : 'Save Social Links'}
            </Button>
          </div>
        </form>
      </Card>

      {user && (
        <SecuritySettingsDialog
          isOpen={isSecurityDialogOpen}
          onClose={() => setIsSecurityDialogOpen(false)}
          onPasswordChanged={() => {
            setStatusMessage({
              type: 'success',
              message: 'Password changed successfully!',
            });
            void checkAuthStatus();
          }}
          on2FAEnabled={() => {
            setStatusMessage({
              type: 'success',
              message: '2FA enabled successfully!',
            });
            void checkAuthStatus();
          }}
          on2FADisabled={() => {
            setStatusMessage({
              type: 'success',
              message: '2FA disabled successfully!',
            });
            void checkAuthStatus();
          }}
          onSessionUpdated={() => {
            setStatusMessage({
              type: 'success',
              message: 'Session length updated.',
            });
            void checkAuthStatus();
          }}
        />
      )}
    </div>
  );
}

export default Profile;
