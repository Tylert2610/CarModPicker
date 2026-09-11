import React, { useState, useEffect } from 'react';
import { Car } from 'lucide-react';

interface ImageWithPlaceholderProps {
  /** The primary image URL to display. */
  srcUrl?: string | null;
  /** Alt text for the image. */
  altText: string;
  /** Text to display if the image source is not provided or fails to load. Defaults to "No image set" */
  fallbackText?: string;
  /** CSS classes to apply to the img tag. */
  imageClassName?: string;
  /** CSS classes to apply to the container div wrapping the image or fallback text. */
  containerClassName?: string;
  /** CSS classes for the fallback text paragraph. */
  fallbackTextClassName?: string;
  /** img loading: "lazy" defers off-screen images (better scroll perf in long lists). */
  loading?: 'lazy' | 'eager';
  /** Fires when the underlying <img> finishes loading. Lets parents read naturalWidth/Height. */
  onLoad?: (e: React.SyntheticEvent<HTMLImageElement>) => void;
}

const DEFAULT_FALLBACK_TEXT = 'No image set';

/** An image that falls back to placeholder text when absent or failing to load. */
const ImageWithPlaceholder: React.FC<ImageWithPlaceholderProps> = ({
  srcUrl,
  altText,
  fallbackText = DEFAULT_FALLBACK_TEXT,
  imageClassName = '',
  containerClassName = '',
  fallbackTextClassName = 'text-gray-400',
  loading = 'eager',
  onLoad,
}) => {
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    setLoadError(false);
  }, [srcUrl]);

  if (!srcUrl || loadError) {
    return (
      <div
        className={`${containerClassName} flex flex-col items-center justify-center gap-2 border border-gray-600 bg-gray-800/50 p-2`}
      >
        <Car
          aria-hidden="true"
          className="h-1/2 max-h-24 w-auto text-gray-500"
          strokeWidth={1.5}
        />
        <p className={`${fallbackTextClassName} text-xs`}>{fallbackText}</p>
      </div>
    );
  }

  return (
    <div className={containerClassName}>
      <img
        src={srcUrl}
        alt={altText}
        className={imageClassName}
        loading={loading}
        decoding="async"
        onError={() => setLoadError(true)}
        onLoad={onLoad}
      />
    </div>
  );
};

export default ImageWithPlaceholder;
