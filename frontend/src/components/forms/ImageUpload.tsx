import React, { useRef, useState } from 'react';
import { imageApi } from '../../api/images';
import type { ImageUploadResponse } from '../../api/images';
import ImageWithPlaceholder from '../images/ImageWithPlaceholder';
import { ErrorAlert } from '../ui/alert';
import Spinner from '../ui/spinner';

interface ImageUploadProps {
  /** Current image URL or file key (S3 object key from upload endpoint) */
  currentImageUrl?: string | null;
  /** Entity type for organizing uploads (e.g., 'build_list', 'part', 'user', 'car') */
  entityType: string;
  /** Optional entity ID for organizing uploads */
  entityId?: string;
  /** Callback when image is successfully uploaded */
  onImageUploaded: (fileKey: string, presignedUrl: string) => void;
  /** Callback when image is removed */
  onImageRemoved?: () => void;
  /** Optional callback when file is selected (before upload). If provided, this bypasses the default upload behavior. */
  onFileSelected?: (file: File) => void | Promise<void>;
  /** Label for the upload input */
  label?: string;
  /** Maximum file size in MB */
  maxSizeMB?: number;
  /** Allowed file extensions */
  allowedExtensions?: string[];
  /** Additional CSS classes */
  className?: string;
  /** Whether to show preview */
  showPreview?: boolean;
  /** Alt text for preview image */
  altText?: string;
}

const DEFAULT_ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp'];

const ImageUpload: React.FC<ImageUploadProps> = ({
  currentImageUrl,
  entityType,
  entityId,
  onImageUploaded,
  onImageRemoved,
  onFileSelected,
  label = 'Image',
  maxSizeMB = 10,
  allowedExtensions = DEFAULT_ALLOWED_EXTENSIONS,
  className = '',
  showPreview = true,
  altText = 'Uploaded image',
}) => {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(
    currentImageUrl || null
  );
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const fileExtension = file.name.split('.').pop()?.toLowerCase();
    if (!fileExtension || !allowedExtensions.includes(fileExtension)) {
      setError(
        `Invalid file type. Allowed types: ${allowedExtensions.join(', ')}`
      );
      return;
    }

    // Validate file size
    const fileSizeMB = file.size / (1024 * 1024);
    if (fileSizeMB > maxSizeMB) {
      setError(`File size exceeds maximum of ${maxSizeMB}MB`);
      return;
    }

    setError(null);
    setIsUploading(true);

    void (async () => {
      try {
        // If onFileSelected is provided, use it instead of default upload
        if (onFileSelected) {
          await onFileSelected(file);
          // Note: onFileSelected is responsible for updating preview and calling onImageUploaded if needed
          // Reset file input
          if (fileInputRef.current) {
            fileInputRef.current.value = '';
          }
          setIsUploading(false);
          return;
        }

        // Default upload behavior
        const response: ImageUploadResponse = await imageApi.uploadImage(
          file,
          entityType,
          entityId
        );

        // Store the file_key in your database, use presigned_url for display
        onImageUploaded(response.file_key, response.presigned_url);
        setPreviewUrl(response.presigned_url);

        // Reset file input
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      } catch (err: unknown) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to upload image';
        setError(errorMessage);
      } finally {
        setIsUploading(false);
      }
    })();
  };

  const handleRemove = () => {
    setPreviewUrl(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    if (onImageRemoved) {
      onImageRemoved();
    }
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {label && (
        <label className="block text-sm font-medium text-foreground">
          {label}
        </label>
      )}

      {error && <ErrorAlert message={error} />}

      {/* Preview */}
      {showPreview && previewUrl && (
        <div className="relative">
          <ImageWithPlaceholder
            srcUrl={previewUrl}
            altText={altText}
            containerClassName="w-full max-w-md rounded-lg overflow-hidden"
            imageClassName="w-full h-auto object-cover"
          />
          {!isUploading && (
            <button
              type="button"
              onClick={handleRemove}
              className="mt-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors text-sm"
            >
              Remove Image
            </button>
          )}
        </div>
      )}

      {/* Upload Input */}
      <div className="space-y-2">
        <input
          ref={fileInputRef}
          type="file"
          accept={allowedExtensions.map((ext) => `.${ext}`).join(',')}
          onChange={handleFileSelect}
          disabled={isUploading}
          className="hidden"
        />
        <button
          type="button"
          onClick={handleClick}
          disabled={isUploading}
          className="w-full px-4 py-3 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center justify-center space-x-2"
        >
          {isUploading ? (
            <React.Fragment>
              <Spinner />
              <span>Uploading...</span>
            </React.Fragment>
          ) : (
            <React.Fragment>
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
              <span>Choose Image</span>
            </React.Fragment>
          )}
        </button>
        <p className="text-xs text-muted-foreground">
          Max size: {maxSizeMB}MB. Allowed: {allowedExtensions.join(', ')}
        </p>
      </div>
    </div>
  );
};

export default ImageUpload;
