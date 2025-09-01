import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  globalPartsApi,
  categoriesApi,
  globalPartVotesApi,
  usersApi,
} from '../../services/Api';
import useApiRequest from '../../hooks/UseApiRequest';
import type {
  GlobalPartReadWithVotes,
  CategoryResponse,
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
import EditGlobalPartForm from '../../components/globalParts/EditGlobalPartForm';
import VoteButtons from '../../components/globalParts/VoteButtons';
import ReportDialog from '../../components/admin/ReportDialog';
import AddToBuildListDialog from '../../components/globalParts/AddToBuildListDialog';

const fetchPartRequestFn = (partId: string) =>
  globalPartsApi.getGlobalPart(Number(partId));

const fetchPartWithVotesRequestFn = (partId: string) =>
  globalPartVotesApi.getVoteSummary(Number(partId));

const fetchCategoriesRequestFn = () => categoriesApi.getCategories();

const fetchUserRequestFn = (userId: number) => usersApi.getUser(userId);

const deletePartRequestFn = (partId: string) =>
  globalPartsApi.deleteGlobalPart(Number(partId));

function ViewGlobalPart() {
  const { partId } = useParams<{ partId: string }>();
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();

  const [isEditGlobalPartFormOpen, setIsEditGlobalPartFormOpen] =
    useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [isReportDialogOpen, setIsReportDialogOpen] = useState(false);
  const [isAddToBuildListDialogOpen, setIsAddToBuildListDialogOpen] =
    useState(false);
  const [partWithVotes, setPartWithVotes] =
    useState<GlobalPartReadWithVotes | null>(null);
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
    data: itemOwner,
    isLoading: isLoadingOwner,
    error: ownerApiError,
    executeRequest: fetchUser,
  } = useApiRequest(fetchUserRequestFn);

  const {
    isLoading: isDeletingPart,
    error: deletePartError,
    executeRequest: executeDeletePart,
    setError: setDeletePartError,
  } = useApiRequest(deletePartRequestFn);

  const memoizedFetchPart = useCallback(() => {
    if (partId) {
      void fetchPart(partId);
    }
  }, [fetchPart, partId]);

  const memoizedFetchVoteSummary = useCallback(() => {
    if (partId) {
      void fetchVoteSummary(partId);
    }
  }, [fetchVoteSummary, partId]);

  const memoizedFetchCategories = useCallback(() => {
    void fetchCategories(undefined);
  }, [fetchCategories]);

  const memoizedFetchUser = useCallback(() => {
    if (part?.user_id) {
      void fetchUser(part.user_id);
    }
  }, [fetchUser, part?.user_id]);

  useEffect(() => {
    memoizedFetchPart();
    memoizedFetchVoteSummary();
    memoizedFetchCategories();
  }, [memoizedFetchPart, memoizedFetchVoteSummary, memoizedFetchCategories]);

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
    memoizedFetchUser();
  }, [memoizedFetchUser]);

  const handleGlobalPartUpdated = async () => {
    if (partId) {
      await fetchPart(partId); // Refresh part data
      await fetchVoteSummary(partId); // Refresh vote data
    }
    setIsEditGlobalPartFormOpen(false);
  };

  const handleVoteUpdate = (
    _partId: number,
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

  const openEditGlobalPartDialog = () => setIsEditGlobalPartFormOpen(true);
  const closeEditGlobalPartDialog = () => setIsEditGlobalPartFormOpen(false);

  const openDeleteConfirmDialog = () => {
    setDeletePartError(null);
    setIsDeleteConfirmOpen(true);
  };
  const closeDeleteConfirmDialog = () => setIsDeleteConfirmOpen(false);

  const openReportDialog = () => setIsReportDialogOpen(true);
  const closeReportDialog = () => setIsReportDialogOpen(false);

  const openAddToBuildListDialog = () => setIsAddToBuildListDialogOpen(true);
  const closeAddToBuildListDialog = () => setIsAddToBuildListDialogOpen(false);

  const handlePartAddedToBuildList = () => {
    console.log('Part added to build list');
  };

  const handleConfirmDelete = async (): Promise<void> => {
    if (!part || !partId) return;

    const result = await executeDeletePart(partId);
    if (result !== null) {
      setIsDeleteConfirmOpen(false);
      void navigate('/global-parts'); // Navigate to global parts catalog
    }
  };

  const isLoading =
    isLoadingPart || isLoadingVotes || isLoadingCategories || isLoadingOwner;

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

  const canEdit =
    currentUser &&
    part &&
    (currentUser.id === part.user_id ||
      currentUser.is_admin ||
      currentUser.is_superuser);

  const canDelete =
    currentUser &&
    part &&
    (currentUser.id === part.user_id ||
      currentUser.is_admin ||
      currentUser.is_superuser);
  const category = categories.find((c) => c.id === part.category_id);

  return (
    <div className="container mx-auto px-4 py-8">
      <PageHeader title={part.name} />
      <Card>
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs bg-green-600 text-white px-2 py-1 rounded-full">
              Global Part
            </span>
          </div>
          <p className="text-sm text-gray-400">
            This is a shared part in the global catalog. You can add it to your
            build lists to create personal copies.
          </p>
        </div>
        <div className="flex justify-between items-center mb-4">
          <SectionHeader title="Part Information" />
          <div className="flex space-x-2">
            {currentUser && (
              <ActionButton
                onClick={openAddToBuildListDialog}
                className="bg-blue-600 hover:bg-blue-700 text-white"
              >
                📋 Add to Build List
              </ActionButton>
            )}
            {currentUser && (
              <ActionButton
                onClick={openReportDialog}
                className="bg-orange-600 hover:bg-orange-700 text-white"
              >
                Report
              </ActionButton>
            )}
            {canEdit && (
              <ActionButton onClick={openEditGlobalPartDialog}>
                Edit Part
              </ActionButton>
            )}
            {canDelete && (
              <ActionButton
                onClick={openDeleteConfirmDialog}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                Delete Part
              </ActionButton>
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
                linkTo={`/user/${itemOwner.id}`}
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
        {ownerApiError && (
          <ErrorAlert
            message={`Error loading creator information: ${ownerApiError}`}
          />
        )}
      </Card>

      <Divider />

      {/* Dialog for Editing Part */}
      {part && canEdit && (
        <Dialog
          isOpen={isEditGlobalPartFormOpen}
          onClose={closeEditGlobalPartDialog}
          title={`Edit ${part.name}`}
        >
          <EditGlobalPartForm
            globalPart={part}
            onGlobalPartUpdated={handleGlobalPartUpdated}
            onCancel={closeEditGlobalPartDialog}
          />
        </Dialog>
      )}

      {/* Dialog for Deleting Part Confirmation */}
      {part && canDelete && (
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

      {/* Dialog for Adding to Build List */}
      {partWithVotes && (
        <AddToBuildListDialog
          isOpen={isAddToBuildListDialogOpen}
          onClose={closeAddToBuildListDialog}
          globalPart={partWithVotes}
          onPartAdded={handlePartAddedToBuildList}
        />
      )}
    </div>
  );
}

export default ViewGlobalPart;
