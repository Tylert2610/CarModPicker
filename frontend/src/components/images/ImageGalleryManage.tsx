import { useState } from 'react';
import { buildExternalImageUrl } from '../../utils/externalImageUrls';
import ImageWithPlaceholder from './ImageWithPlaceholder';
import { ErrorAlert } from '../ui/alert';
import { ConfirmDialog } from '../ui/confirm-dialog';

const CAROUSEL_SIZE = 5;

interface ImageGalleryManageProps {
  /** Image URLs (presigned from API). First entry is the primary/display image. */
  imageUrls?: string[] | null;
  altText: string;
  /** Set the image at index as the primary image. */
  onSetPrimary: (index: number) => Promise<unknown>;
  /** Remove the image at index. */
  onRemove: (index: number) => Promise<unknown>;
  /** Called after a successful set-primary or remove so the parent can refresh. */
  onUpdated: () => void | Promise<void>;
  /** When "hero", show large primary image with carousel of others beneath */
  layout?: 'carousel' | 'hero';
  /** Custom message when no images are available */
  emptyMessage?: string;
}

/**
 * Displays images with management actions for users with edit permission:
 * set primary image, remove image. Supports carousel (default) or hero layout.
 * Entity-agnostic — caller wires the API via onSetPrimary / onRemove.
 */
export default function ImageGalleryManage({
  imageUrls,
  altText,
  onSetPrimary,
  onRemove,
  onUpdated,
  layout = 'carousel',
  emptyMessage = 'No images available.',
}: ImageGalleryManageProps) {
  const [showAll, setShowAll] = useState(false);
  const [removeDialogOpen, setRemoveDialogOpen] = useState(false);
  const [imageIndexToRemove, setImageIndexToRemove] = useState<number | null>(
    null
  );
  const [isRemoving, setIsRemoving] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const [settingPrimaryIndex, setSettingPrimaryIndex] = useState<number | null>(
    null
  );
  const [selectedIndex, setSelectedIndex] = useState(0);

  const allUrls = imageUrls && imageUrls.length > 0 ? imageUrls : [];

  const handleSetPrimary = async (index: number) => {
    if (index < 0 || index >= allUrls.length) return;
    setSettingPrimaryIndex(index);
    setRemoveError(null);
    try {
      await onSetPrimary(index);
      await onUpdated();
    } catch (e) {
      setRemoveError(
        e instanceof Error ? e.message : 'Failed to set primary image'
      );
    } finally {
      setSettingPrimaryIndex(null);
    }
  };

  const openRemoveDialog = (index: number) => {
    setImageIndexToRemove(index);
    setRemoveError(null);
    setRemoveDialogOpen(true);
  };

  const closeRemoveDialog = () => {
    setRemoveDialogOpen(false);
    setImageIndexToRemove(null);
    setRemoveError(null);
  };

  const handleConfirmRemove = async () => {
    if (imageIndexToRemove == null) return;
    setIsRemoving(true);
    setRemoveError(null);
    try {
      await onRemove(imageIndexToRemove);
      await onUpdated();
      closeRemoveDialog();
    } catch (e) {
      setRemoveError(e instanceof Error ? e.message : 'Failed to remove image');
    } finally {
      setIsRemoving(false);
    }
  };

  if (allUrls.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center border border-gray-600 bg-gray-800/50 rounded-lg p-4">
        <p className="text-gray-400">{emptyMessage}</p>
      </div>
    );
  }

  if (layout === 'hero') {
    const displayIndex = Math.min(selectedIndex, allUrls.length - 1);
    const selectedUrl = allUrls[displayIndex];
    const isSelectedPrimary = displayIndex === 0;
    const isSettingPrimarySelected = settingPrimaryIndex === displayIndex;

    return (
      <div className="space-y-3">
        {removeError && <ErrorAlert message={removeError} />}
        <div className="aspect-[4/3] max-h-[420px] w-full rounded-lg overflow-hidden border border-gray-600 bg-gray-800/50 relative group">
          <ImageWithPlaceholder
            srcUrl={buildExternalImageUrl(selectedUrl, 'hero')}
            altText={`${altText} - image ${displayIndex + 1}`}
            imageClassName="w-full h-full object-contain"
            containerClassName="w-full h-full"
            fallbackText="Failed to load"
          />
          <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2 p-2">
            {isSelectedPrimary ? (
              <span className="text-xs font-medium text-success bg-success/80 px-2 py-1 rounded">
                Primary
              </span>
            ) : (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  void handleSetPrimary(displayIndex);
                }}
                disabled={isSettingPrimarySelected}
                className="text-xs font-medium text-white bg-primary hover:bg-primary px-2 py-1 rounded border border-white/80 disabled:opacity-50"
              >
                {isSettingPrimarySelected ? 'Updating…' : 'Set as primary'}
              </button>
            )}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                openRemoveDialog(displayIndex);
              }}
              className="text-xs font-medium text-white bg-red-600 hover:bg-red-500 px-2 py-1 rounded"
            >
              Remove
            </button>
          </div>
        </div>
        {allUrls.length > 1 && (
          <div className="flex gap-3 overflow-x-auto pb-2 rounded-lg">
            {allUrls.map((url, idx) => {
              const isSettingPrimary = settingPrimaryIndex === idx;
              const isSelected = idx === displayIndex;
              return (
                <div
                  key={url}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedIndex(idx)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setSelectedIndex(idx);
                    }
                  }}
                  className={`shrink-0 w-24 h-24 rounded-lg overflow-hidden border-2 bg-gray-800/50 relative group cursor-pointer transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-gray-900 ${
                    isSelected
                      ? 'border-primary ring-2 ring-primary/50'
                      : 'border-gray-600 hover:border-gray-500'
                  }`}
                >
                  <ImageWithPlaceholder
                    srcUrl={buildExternalImageUrl(url, 'thumbnail')}
                    altText={`${altText} - image ${idx + 1}`}
                    imageClassName="w-full h-full object-cover"
                    containerClassName="w-full h-full"
                    fallbackText="Failed to load"
                    loading="lazy"
                  />
                  <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2 p-2">
                    {idx === 0 ? (
                      <span className="text-xs font-medium text-success bg-success/80 px-2 py-1 rounded">
                        Primary
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          void handleSetPrimary(idx);
                        }}
                        disabled={isSettingPrimary}
                        className="text-xs font-medium text-white bg-primary hover:bg-primary px-2 py-1 rounded border border-white/80 disabled:opacity-50"
                      >
                        {isSettingPrimary ? 'Updating…' : 'Set as primary'}
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        openRemoveDialog(idx);
                      }}
                      className="text-xs font-medium text-white bg-red-600 hover:bg-red-500 px-2 py-1 rounded"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        <ConfirmDialog
          open={removeDialogOpen}
          onOpenChange={(open) => {
            if (!open && isRemoving) return;
            if (!open) closeRemoveDialog();
          }}
          onConfirm={() => void handleConfirmRemove()}
          title="Confirm Deletion"
          description="Are you sure you want to delete this image? This action cannot be undone."
          confirmLabel="Confirm Delete"
          loadingLabel="Deleting..."
          variant="destructive"
          loading={isRemoving}
          error={removeError}
        />
      </div>
    );
  }

  const visibleUrls = showAll ? allUrls : allUrls.slice(0, CAROUSEL_SIZE);
  const hasMore = allUrls.length > CAROUSEL_SIZE;
  const remainingCount = allUrls.length - CAROUSEL_SIZE;

  return (
    <div className="space-y-3">
      {removeError && <ErrorAlert message={removeError} />}
      <div
        className={
          showAll
            ? 'grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3'
            : 'flex gap-3 overflow-x-auto pb-2 rounded-lg'
        }
      >
        {visibleUrls.map((url, idx) => {
          const imageIndex = idx;
          const isPrimary = imageIndex === 0;
          const isSettingPrimary = settingPrimaryIndex === imageIndex;

          return (
            <div
              key={`${url}-${imageIndex}`}
              className={
                showAll
                  ? 'aspect-square rounded-lg overflow-hidden border border-gray-600 bg-gray-800/50 relative group'
                  : 'shrink-0 w-40 h-40 rounded-lg overflow-hidden border border-gray-600 bg-gray-800/50 relative group'
              }
            >
              <ImageWithPlaceholder
                srcUrl={buildExternalImageUrl(url, 'carouselTile')}
                altText={`${altText} - image ${imageIndex + 1}`}
                imageClassName="w-full h-full object-cover"
                containerClassName="w-full h-full"
                fallbackText="Failed to load"
                loading="lazy"
              />
              <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2 p-2">
                {isPrimary ? (
                  <span className="text-xs font-medium text-success bg-success/80 px-2 py-1 rounded">
                    Primary
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => void handleSetPrimary(imageIndex)}
                    disabled={isSettingPrimary}
                    className="text-xs font-medium text-white bg-primary hover:bg-primary px-2 py-1 rounded disabled:opacity-50"
                  >
                    {isSettingPrimary ? 'Updating…' : 'Set as primary'}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => openRemoveDialog(imageIndex)}
                  className="text-xs font-medium text-white bg-red-600 hover:bg-red-500 px-2 py-1 rounded"
                >
                  Remove
                </button>
              </div>
            </div>
          );
        })}
      </div>
      {hasMore && !showAll && (
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className="text-sm text-primary hover:text-primary/90 font-medium transition-colors"
        >
          Show {remainingCount} more image{remainingCount !== 1 ? 's' : ''}
        </button>
      )}
      {hasMore && showAll && (
        <button
          type="button"
          onClick={() => setShowAll(false)}
          className="text-sm text-gray-400 hover:text-gray-300 font-medium transition-colors"
        >
          Show less
        </button>
      )}

      <ConfirmDialog
        open={removeDialogOpen}
        onOpenChange={(open) => {
          if (!open && isRemoving) return;
          if (!open) closeRemoveDialog();
        }}
        onConfirm={() => void handleConfirmRemove()}
        title="Confirm Deletion"
        description="Are you sure you want to delete this image? This action cannot be undone."
        confirmLabel="Confirm Delete"
        loadingLabel="Deleting..."
        variant="destructive"
        loading={isRemoving}
        error={removeError}
      />
    </div>
  );
}
