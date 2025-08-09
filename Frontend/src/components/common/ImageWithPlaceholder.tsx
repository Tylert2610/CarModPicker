import React, { useState, useEffect } from 'react';

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
}

const DEFAULT_FALLBACK_TEXT = 'No image set';

const ImageWithPlaceholder: React.FC<ImageWithPlaceholderProps> = ({
  srcUrl,
  altText,
  fallbackText = DEFAULT_FALLBACK_TEXT,
  imageClassName = '',
  containerClassName = '',
  fallbackTextClassName = 'text-gray-400',
}) => {
  const [showFallback, setShowFallback] = useState(false);
  const [imageSrc, setImageSrc] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (srcUrl) {
      setImageSrc(srcUrl);
      setShowFallback(false);
    } else {
      setImageSrc(undefined);
      setShowFallback(true);
    }
  }, [srcUrl]);

  const handleError = () => {
    // If the srcUrl fails to load, show fallback text
    setShowFallback(true);
  };

  if (showFallback || !imageSrc) {
    return (
      <div
        className={`${containerClassName} flex items-center justify-center border border-gray-400 p-2`}
      >
        <p className={fallbackTextClassName}>{fallbackText}</p>
      </div>
    );
  }

  return (
    <div className={containerClassName}>
      <img
        src={imageSrc}
        alt={altText}
        className={imageClassName}
        onError={handleError}
      />
    </div>
  );
};

export default ImageWithPlaceholder;
