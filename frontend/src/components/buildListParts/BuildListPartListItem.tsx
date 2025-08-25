import React from 'react';
import { Link } from 'react-router-dom';
import type { BuildListPartReadWithGlobalPart } from '../../types/Api';
import Card from '../common/Card';
import CardInfoItem from '../common/CardInfoItem';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';
import ActionButton from '../buttons/ActionButton';
import SecondaryButton from '../buttons/SecondaryButton';

interface BuildListPartListItemProps {
  buildListPart: BuildListPartReadWithGlobalPart;
  onEdit?: (buildListPart: BuildListPartReadWithGlobalPart) => void;
  onDelete?: (buildListPartId: number) => void;
  canEdit?: boolean;
  canDelete?: boolean;
}

const BuildListPartListItem: React.FC<BuildListPartListItemProps> = ({
  buildListPart,
  onEdit,
  onDelete,
  canEdit = false,
  canDelete = false,
}) => {
  const { global_part, notes, added_at } = buildListPart;

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const formatPrice = (price: number | null | undefined) => {
    if (price === null || price === undefined) return 'Price not specified';
    return `$${price.toLocaleString()}`;
  };

  return (
    <Card>
      <div className="flex flex-col md:flex-row gap-4">
        {/* Image */}
        <div className="flex-shrink-0">
          <ImageWithPlaceholder
            srcUrl={global_part.image_url}
            altText={`${global_part.name} image`}
            imageClassName="w-32 h-32 object-cover rounded-lg"
          />
        </div>

        {/* Content */}
        <div className="flex-grow">
          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-2">
            <div className="flex-grow">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs bg-blue-600 text-white px-2 py-1 rounded-full">
                  Build List Copy
                </span>
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">
                <Link
                  to={`/global-parts/${global_part.id}`}
                  className="hover:text-blue-400 transition-colors"
                >
                  {global_part.name}
                </Link>
              </h3>

              {global_part.description && (
                <p className="text-gray-300 mb-3 line-clamp-2">
                  {global_part.description}
                </p>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-3">
                <CardInfoItem label="Price">
                  {formatPrice(global_part.price)}
                </CardInfoItem>
                <CardInfoItem label="Brand">
                  {global_part.brand || 'Not specified'}
                </CardInfoItem>
                <CardInfoItem label="Part Number">
                  {global_part.part_number || 'Not specified'}
                </CardInfoItem>
                <CardInfoItem label="Added">
                  {formatDate(added_at)}
                </CardInfoItem>
              </div>

              {notes && (
                <div className="mb-3">
                  <h4 className="text-sm font-medium text-gray-400 mb-1">
                    📝 Your Notes (Build List Copy):
                  </h4>
                  <p className="text-gray-300 text-sm bg-gray-800 p-2 rounded">
                    {notes}
                  </p>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex flex-col gap-2">
              {canEdit && onEdit && (
                <SecondaryButton
                  onClick={() => onEdit(buildListPart)}
                  className="w-full md:w-auto"
                >
                  Edit Notes
                </SecondaryButton>
              )}
              {canDelete && onDelete && (
                <ActionButton
                  onClick={() => onDelete(buildListPart.id)}
                  className="w-full md:w-auto bg-red-600 hover:bg-red-700"
                >
                  Remove from Build List
                </ActionButton>
              )}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
};

export default BuildListPartListItem;
