import React from 'react';
import type { BuildListPartReadWithGlobalPart } from '../../types/Api';
import BuildListPartListItem from './BuildListPartListItem';
import LoadingSpinner from '../common/LoadingSpinner';
import Card from '../common/Card';

interface BuildListPartListProps {
  buildListParts: BuildListPartReadWithGlobalPart[];
  loading?: boolean;
  onEdit?: (buildListPart: BuildListPartReadWithGlobalPart) => void;
  onDelete?: (buildListPartId: number) => void;
  canEdit?: boolean;
  canDelete?: boolean;
  canEditPart?: (buildListPart: BuildListPartReadWithGlobalPart) => boolean;
  canDeletePart?: (buildListPart: BuildListPartReadWithGlobalPart) => boolean;
  emptyMessage?: string;
}

const BuildListPartList: React.FC<BuildListPartListProps> = ({
  buildListParts,
  loading = false,
  onEdit,
  onDelete,
  canEdit = false,
  canDelete = false,
  canEditPart,
  canDeletePart,
  emptyMessage = 'No parts added to this build list yet.',
}) => {
  if (loading) {
    return (
      <div className="flex justify-center items-center py-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (buildListParts.length === 0) {
    return (
      <Card>
        <div className="text-center py-8">
          <p className="text-gray-400 text-lg">{emptyMessage}</p>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {buildListParts.map((buildListPart) => (
        <BuildListPartListItem
          key={buildListPart.id}
          buildListPart={buildListPart}
          onEdit={onEdit}
          onDelete={onDelete}
          canEdit={canEdit && (!canEditPart || canEditPart(buildListPart))}
          canDelete={
            canDelete && (!canDeletePart || canDeletePart(buildListPart))
          }
        />
      ))}
    </div>
  );
};

export default BuildListPartList;
