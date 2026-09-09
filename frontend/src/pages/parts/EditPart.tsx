import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import useApiRequest from '../../hooks/UseApiRequest';
import { useAuth } from '../../hooks/useAuth';
import { partsApi } from '../../api/parts';

import EditPartForm from '../../components/parts/EditPartForm';
import PageHeader from '../../components/layout/PageHeader';
import { ErrorAlert } from '../../components/ui/alert';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/card';
import Spinner from '../../components/ui/spinner';

const fetchPartRequestFn = (partId: string) => partsApi.getPart(partId);

function EditPart() {
  const { partId } = useParams<{ partId: string }>();
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();

  const {
    data: part,
    isLoading: isLoadingPart,
    error: partApiError,
    executeRequest: fetchPart,
  } = useApiRequest(fetchPartRequestFn);

  useEffect(() => {
    if (partId) {
      void fetchPart(partId);
    }
  }, [partId, fetchPart]);

  const handlePartUpdated = async () => {
    if (partId) {
      await fetchPart(partId);
      // Navigate back to the part view page
      void navigate(`/parts/${partId}`);
    }
  };

  const handleCancel = () => {
    if (partId) {
      void navigate(`/parts/${partId}`);
    } else {
      void navigate('/');
    }
  };

  if (isLoadingPart) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Edit Part" />
        <Card>
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        </Card>
      </div>
    );
  }

  if (partApiError) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Edit Part" />
        <Card>
          <ErrorAlert message={`Failed to load part: ${partApiError}`} />
          <div className="mt-4">
            <Button type="button" variant="secondary" onClick={handleCancel}>
              Go Back
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  if (!part) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Edit Part" />
        <Card>
          <ErrorAlert message="Part not found." />
          <div className="mt-4">
            <Button type="button" variant="secondary" onClick={handleCancel}>
              Go Back
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  // Check if user can edit this part
  const canEdit =
    currentUser &&
    (currentUser.id === part.user_id ||
      currentUser.is_admin ||
      currentUser.is_superuser);

  if (!canEdit) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Edit Part" />
        <Card>
          <ErrorAlert message="You don't have permission to edit this part." />
          <div className="mt-4">
            <Button type="button" variant="secondary" onClick={handleCancel}>
              Go Back
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  // Safety check - ensure part has required fields
  if (!part || !part.id || !part.name) {
    return (
      <div className="container mx-auto px-4 py-8">
        <PageHeader title="Edit Part" />
        <Card>
          <ErrorAlert message="Invalid part data received. Please try again." />
          <div className="mt-4">
            <Button type="button" variant="secondary" onClick={handleCancel}>
              Go Back
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader title={`Edit ${part.name}`} />
      <Card>
        <EditPartForm
          part={part}
          onPartUpdated={handlePartUpdated}
          onCancel={handleCancel}
        />
      </Card>
    </div>
  );
}

export default EditPart;
