import React from 'react';
import { Link } from 'react-router-dom';
import type { PartRead } from '../../types/Api';
import { buildExternalImageUrl } from '../../utils/externalImageUrls';
import ImageWithPlaceholder from '../images/ImageWithPlaceholder';
import { Card } from '../ui/card';

interface PartListItemProps {
  part: PartRead;
}

/** A part as a compact row with its price. */
const PartListItem: React.FC<PartListItemProps> = ({ part }) => {
  return (
    <Link to={`/parts/${part.id}`} className="block hover:no-underline">
      <Card className="flex flex-row items-start gap-4 p-4 border-2 border-transparent w-full">
        <ImageWithPlaceholder
          srcUrl={buildExternalImageUrl(part.image_urls?.[0], 'thumbnail')}
          altText={part.name}
          imageClassName="w-24 h-24 object-cover rounded-md"
          containerClassName="w-24 h-24 flex-shrink-0"
          fallbackText="No image"
        />
        <div className="flex-grow flex flex-col justify-start">
          <h3 className="text-xl font-semibold text-gray-200 mb-1 truncate">
            {part.name}
          </h3>
          {part.part_manufacturer && (
            <p className="text-sm text-gray-400">
              By: {part.part_manufacturer}
            </p>
          )}
          <div className="flex justify-between items-center mt-2 text-sm">
            {part.part_number && (
              <div>
                <span className="text-gray-500 font-medium">P/N: </span>
                <span className="text-gray-300 truncate">
                  {part.part_number}
                </span>
              </div>
            )}

            {part.best_price_cents != null && (
              <div>
                <span className="text-gray-300 font-semibold text-lg">
                  ${(part.best_price_cents / 100).toFixed(2)}
                </span>
              </div>
            )}
          </div>
        </div>
      </Card>
    </Link>
  );
};

export default PartListItem;
