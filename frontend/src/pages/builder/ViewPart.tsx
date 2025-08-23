import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { partsApi, categoriesApi, partVotesApi } from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type {
  PartReadWithVotes,
  CategoryResponse,
  UserRead,
} from '../../types/Api';
import { useAuth } from '../../hooks/useAuth';

import PageHeader from '../../components/layout/PageHeader';
import Card from '../../components/common/Card';
import SectionHeader from '../../components/layout/SectionHeader';
import CardInfoItem from '../../components/common/CardInfoItem';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import { ErrorAlert } from '../../components/common/Alerts';
import Divider from '../../components/layout/Divider';
import Dialog from '../../components/common/Dialog';
import ActionButton from '../../components/buttons/ActionButton';
import ParentNavigationLink from '../../components/common/ParentNavigationLink';
import ImageWithPlaceholder from '../../components/common/ImageWithPlaceholder';
import DeleteConfirmationDialog from '../../components/common/DeleteConfirmationDialog';
import EditPartForm from '../../components/parts/EditPartForm';
import VoteButtons from '../../components/parts/VoteButtons';
import ReportDialog from '../../components/admin/ReportDialog';

const fetchPartRequestFn = (partId: string) => partsApi.getPart(Number(partId));

const fetchPartWithVotesRequestFn = (partId: string) =>
  partVotesApi.getVoteSummary(Number(partId));

const fetchCategoriesRequestFn = () => categoriesApi.getCategories();

const deletePartRequestFn = (partId: string) =>
  partsApi.deletePart(Number(partId));

function ViewPart() {
  const { partId } = useParams<{ partId: string }>();
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();

  const [isEditPartFormOpen, setIsEditPartFormOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [isReportDialogOpen, setIsReportDialogOpen] = useState(false);
  const [itemOwner, setItemOwner] = useState<UserRead | null>(null);
  const [partWithVotes, setPartWithVotes] = useState<PartReadWithVotes | null>(
    null
  );
  const [categories, setCategories] = useState<CategoryResponse[]>([]);

  const {
    data: part,
    isLoading: isLoadingPart,
    error: partApiError,
    executeRequest: fetchPart,
  } = useApiRequest(fetchPartRequestFn);

  const {
    data: voteSummary,
    isLoading: isLoadingVotes,
    error: voteApiError,
    executeRequest: fetchVoteSummary,
  } = useApiRequest(fetchPartWithVotesRequestFn);

  const {
    data: categoriesData,
    isLoading: isLoadingCategories,
    error: categoriesApiError,
    executeRequest: fetchCategories,
  } = useApiRequest(fetchCategoriesRequestFn);

  const {
    isLoading: isDeletingPart,
    error: deletePartError,
    executeRequest: executeDeletePart,
    setError: setDeletePartError,
  } = useApiRequest<void, string>(deletePartRequestFn);

  useEffect(() => {
    if (partId) {
      void fetchPart(partId);
      void fetchVoteSummary(partId);
      void fetchCategories();
    }
  }, [partId, fetchPart, fetchVoteSummary, fetchCategories]);

  useEffect(() => {
    if (categoriesData) {
      setCategories(categoriesData);
    }
  }, [categoriesData]);

  useEffect(() => {
    if (part && voteSummary) {
      setPartWithVotes({
        ...part,
        upvotes: voteSummary.upvotes,
        downvotes: voteSummary.downvotes,
        total_votes: voteSummary.total_votes,
        user_vote: voteSummary.user_vote,
      });
    }
  }, [part, voteSummary]);

  useEffect(() => {
    if (part?.user_id) {
      // For now, we'll skip fetching user data since the API call is incorrect
      // TODO: Fix this when usersApi is properly implemented
    }
  }, [part?.user_id]);

  const handlePartUpdated = async () => {
    if (partId) {
      await fetchPart(partId); // Refresh part data
      await fetchVoteSummary(partId); // Refresh vote data
    }
    setIsEditPartFormOpen(false);
  };

  const handleVoteUpdate = (
    partId: number,
    newVote: 'upvote' | 'downvote' | null
  ) => {
    if (partWithVotes) {
      const currentVote = partWithVotes.user_vote;
      let upvotes = partWithVotes.upvotes;
      let downvotes = partWithVotes.downvotes;

      // Remove previous vote
      if (currentVote === 'upvote') upvotes--;
      if (currentVote === 'downvote') downvotes--;

      // Add new vote
      if (newVote === 'upvote') upvotes++;
      if (newVote === 'downvote') downvotes++;

      setPartWithVotes({
        ...partWithVotes,
        upvotes,
        downvotes,
        total_votes: upvotes + downvotes,
        user_vote: newVote,
      });
    }
  };

  const openEditPartDialog = () => setIsEditPartFormOpen(true);
  const closeEditPartDialog = () => setIsEditPartFormOpen(false);

  const openDeleteConfirmDialog = () => {
    setDeletePartError(null);
    setIsDeleteConfirmOpen(true);
  };
  const closeDeleteConfirmDialog = () => setIsDeleteConfirmOpen(false);

  const openReportDialog = () => setIsReportDialogOpen(true);
  const closeReportDialog = () => setIsReportDialogOpen(false);

  const handleConfirmDelete = async (): Promise<void> => {
    if (!part || !partId) return;

    const result = await executeDeletePart(partId);
    if (result !== null) {
      setIsDeleteConfirmOpen(false);
      void navigate('/parts'); // Navigate to parts catalog
    }
  };

  const isLoading = isLoadingPart || isLoadingVotes || isLoadingCategories;

  if (isLoading && !part) {
    return (
      <>
        <PageHeader title="Part Details" />
        <LoadingSpinner />
      </>
    );
  }

  if (partApiError) {
    return (
      <div>
        <PageHeader title="Part Details" />
        <Card>
          <ErrorAlert
            message={`Failed to load part with ID "${partId}". ${partApiError}`}
          />
        </Card>
      </div>
    );
  }

  if (!part) {
    return (
      <div>
        <PageHeader title="Part Details" />
        <Card>
          <ErrorAlert message={`Part with ID "${partId}" not found.`} />
        </Card>
      </div>
    );
  }

  const canManage = currentUser && itemOwner && currentUser.id === itemOwner.id;
  const category = categories.find((c) => c.id === part.category_id);

  return (
    <div>
      <PageHeader title={part.name} />
      <Card>
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title="Part Information" />
          <div className="flex space-x-2">
            {currentUser && (
              <ActionButton
                onClick={openReportDialog}
                className="bg-orange-600 hover:bg-orange-700 text-white"
              >
                Report
              </ActionButton>
            )}
            {canManage && (
              <>
                <ActionButton onClick={openEditPartDialog}>
                  Edit Part
                </ActionButton>
                <ActionButton
                  onClick={openDeleteConfirmDialog}
                  className="bg-red-600 hover:bg-red-700 text-white"
                >
                  Delete Part
                </ActionButton>
              </>
            )}
          </div>
        </div>

        {/* Voting Section */}
        {partWithVotes && (
          <div className="mb-6 p-4 bg-gray-800 rounded-lg">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white">
                Community Rating
              </h3>
              <VoteButtons
                partId={part.id}
                upvotes={partWithVotes.upvotes}
                downvotes={partWithVotes.downvotes}
                userVote={partWithVotes.user_vote}
                onVoteUpdate={handleVoteUpdate}
                size="lg"
              />
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-300 mb-6">
          <CardInfoItem label="Part Image">
            <ImageWithPlaceholder
              srcUrl={part.image_url}
              altText={part.name}
              imageClassName="h-48 w-auto object-contain rounded"
              containerClassName="h-48 flex justify-left items-center"
              fallbackText="No image available for this part."
            />
          </CardInfoItem>
          <div className="hidden md:block"></div> {/* Spacer */}
          {part.description && (
            <CardInfoItem label="Description:">
              <p className="whitespace-pre-wrap">{part.description}</p>
            </CardInfoItem>
          )}
          {category && (
            <CardInfoItem label="Category:">
              <p className="text-blue-400">{category.display_name}</p>
            </CardInfoItem>
          )}
          {part.brand && (
            <CardInfoItem label="Brand:">
              <p>{part.brand}</p>
            </CardInfoItem>
          )}
          {part.part_number && (
            <CardInfoItem label="Part Number:">
              <p>{part.part_number}</p>
            </CardInfoItem>
          )}
          {part.price !== null && part.price !== undefined && (
            <CardInfoItem label="Price:">
              <p>${part.price.toLocaleString()}</p>
            </CardInfoItem>
          )}
          {part.specifications &&
            Object.keys(part.specifications).length > 0 && (
              <CardInfoItem label="Specifications:">
                <div className="space-y-1">
                  {Object.entries(part.specifications).map(([key, value]) => (
                    <div key={key} className="flex justify-between">
                      <span className="font-medium">{key}:</span>
                      <span>{String(value)}</span>
                    </div>
                  ))}
                </div>
              </CardInfoItem>
            )}
          <CardInfoItem label="Status:">
            <div className="flex items-center space-x-2">
              {part.is_verified && (
                <span className="text-green-400 text-sm">✓ Verified</span>
              )}
              <span className="text-gray-400 text-sm">
                Source: {part.source}
              </span>
            </div>
          </CardInfoItem>
          <CardInfoItem label="Edit History:">
            <p>{part.edit_count} edits</p>
          </CardInfoItem>
          {itemOwner && (
            <CardInfoItem label="Created by:">
              <ParentNavigationLink
                linkTo={`/users/${itemOwner.id}`}
                linkText={itemOwner.username}
              />
            </CardInfoItem>
          )}
          <CardInfoItem label="Created:">
            <p>{new Date(part.created_at).toLocaleDateString()}</p>
          </CardInfoItem>
          <CardInfoItem label="Last Updated:">
            <p>{new Date(part.updated_at).toLocaleDateString()}</p>
          </CardInfoItem>
        </div>

        {voteApiError && (
          <ErrorAlert message={`Error loading vote data: ${voteApiError}`} />
        )}
        {categoriesApiError && (
          <ErrorAlert
            message={`Error loading category data: ${categoriesApiError}`}
          />
        )}
      </Card>

      <Divider />

      {/* Dialog for Editing Part */}
      {part && canManage && (
        <Dialog
          isOpen={isEditPartFormOpen}
          onClose={closeEditPartDialog}
          title={`Edit ${part.name}`}
        >
          <EditPartForm
            part={part}
            onPartUpdated={handlePartUpdated}
            onCancel={closeEditPartDialog}
          />
        </Dialog>
      )}

      {/* Dialog for Deleting Part Confirmation */}
      {part && canManage && (
        <DeleteConfirmationDialog
          isOpen={isDeleteConfirmOpen}
          onClose={closeDeleteConfirmDialog}
          onConfirm={() => void handleConfirmDelete()}
          itemName={part.name}
          itemType="part"
          isProcessing={isDeletingPart}
          error={deletePartError}
        />
      )}

      {/* Dialog for Reporting Part */}
      {part && (
        <ReportDialog
          isOpen={isReportDialogOpen}
          onClose={closeReportDialog}
          partId={part.id}
          partName={part.name}
        />
      )}
    </div>
  );
}

export default ViewPart;
