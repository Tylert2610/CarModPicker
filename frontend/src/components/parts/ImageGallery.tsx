import { useEffect, useState } from 'react';
import ImageWithPlaceholder from '../images/ImageWithPlaceholder';
import { buildExternalImageUrl } from '../../utils/externalImageUrls';

const CAROUSEL_SIZE = 5;
const DEFAULT_HERO_ASPECT = 4 / 3;
const MIN_HERO_ASPECT = 3 / 4;
const MAX_HERO_ASPECT = 16 / 9;

interface ImageGalleryProps {
  /** Image URLs (presigned from API). First entry is the primary/display image. */
  imageUrls?: string[] | null;
  altText: string;
  /** When "hero", show large primary image with carousel of others beneath */
  layout?: 'carousel' | 'hero';
  /** Custom message when no images are available */
  emptyMessage?: string;
}

/**
 * Displays part images: carousel (default) or hero (large primary + carousel of others).
 */
function ImageGallery({
  imageUrls,
  altText,
  layout = 'carousel',
  emptyMessage = 'No images available for this part.',
}: ImageGalleryProps) {
  const [showAll, setShowAll] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [heroAspect, setHeroAspect] = useState<number>(DEFAULT_HERO_ASPECT);

  const allUrls = imageUrls && imageUrls.length > 0 ? imageUrls : [];

  useEffect(() => {
    setHeroAspect(DEFAULT_HERO_ASPECT);
  }, [selectedIndex]);

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

    return (
      <div className="space-y-3">
        <div
          className="max-h-[420px] w-full rounded-lg overflow-hidden border border-gray-600 bg-gray-800/50"
          style={{ aspectRatio: heroAspect }}
        >
          <ImageWithPlaceholder
            srcUrl={buildExternalImageUrl(selectedUrl, 'hero')}
            altText={`${altText} - image ${displayIndex + 1}`}
            imageClassName="w-full h-full object-contain"
            containerClassName="w-full h-full"
            fallbackText="Failed to load"
            onLoad={(e) => {
              const img = e.currentTarget;
              if (img.naturalWidth && img.naturalHeight) {
                const ratio = img.naturalWidth / img.naturalHeight;
                setHeroAspect(
                  Math.max(MIN_HERO_ASPECT, Math.min(MAX_HERO_ASPECT, ratio))
                );
              }
            }}
          />
        </div>
        {allUrls.length > 1 && (
          <div className="flex gap-3 overflow-x-auto pb-2 rounded-lg">
            {allUrls.map((url, idx) => (
              <button
                type="button"
                key={url}
                onClick={() => setSelectedIndex(idx)}
                className={`shrink-0 w-24 h-24 rounded-lg overflow-hidden border-2 bg-gray-800/50 transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-gray-900 ${
                  idx === displayIndex
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
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  const visibleUrls = showAll ? allUrls : allUrls.slice(0, CAROUSEL_SIZE);
  const hasMore = allUrls.length > CAROUSEL_SIZE;
  const remainingCount = allUrls.length - CAROUSEL_SIZE;

  return (
    <div className="space-y-3">
      <div
        className={
          showAll
            ? 'grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3'
            : 'flex gap-3 overflow-x-auto pb-2 rounded-lg'
        }
      >
        {visibleUrls.map((url, idx) => (
          <div
            key={url}
            className={
              showAll
                ? 'aspect-square rounded-lg overflow-hidden border border-gray-600 bg-gray-800/50'
                : 'shrink-0 w-40 h-40 rounded-lg overflow-hidden border border-gray-600 bg-gray-800/50'
            }
          >
            <ImageWithPlaceholder
              srcUrl={buildExternalImageUrl(url, 'carouselTile')}
              altText={`${altText} - image ${idx + 1}`}
              imageClassName="w-full h-full object-cover"
              containerClassName="w-full h-full"
              fallbackText="Failed to load"
              loading="lazy"
            />
          </div>
        ))}
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
    </div>
  );
}

export default ImageGallery;
