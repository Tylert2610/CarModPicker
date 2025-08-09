import React from 'react';
import { Link } from 'react-router-dom';
import type { PartRead } from '../../types/Api';
import Card from '../common/Card';
import ImageWithPlaceholder from '../common/ImageWithPlaceholder';

interface PartListItemProps {
  part: PartRead;
}

const PartListItem: React.FC<PartListItemProps> = ({ part }) => {
  return (
    <Link
      to={`/parts/${part.id}`}
      className="block hover:no-underline" 
    >
      <Card className="flex flex-row items-start gap-4 p-4 hover:border-indigo-500 border-2 border-transparent transition-colors w-full">
        <ImageWithPlaceholder
          srcUrl={part.image_url}
          altText={part.name}
          imageClassName="w-24 h-24 object-cover rounded-md" 
          containerClassName="w-24 h-24 flex-shrink-0"    
          fallbackText="No image"
        />
        <div className="flex-grow flex flex-col justify-start">
          <h3 className="text-xl font-semibold text-indigo-400 mb-1 truncate">
            {part.name}
          </h3>
          {part.manufacturer && (
            <p className="text-md text-gray-400 mb-1 truncate">
              By: {part.manufacturer}
            </p>
          )}
          <div className="flex justify-between items-center mt-2 text-sm"> 
            {part.part_number && (
              <div>
                <span className="text-gray-500 font-medium">P/N: </span>
                <span className="text-gray-300 truncate">{part.part_number}</span>
              </div>
            )}
           
            {part.price !== null && part.price !== undefined && (
              <div>
                {/* Optional: you can remove the "Price: " label if it's implied */}
                <span className="text-gray-300 font-semibold text-lg">${part.price.toFixed(2)}</span>
              </div>
            )}
          </div>
          
        </div>
      </Card>
    </Link>
  );
};

export default PartListItem;
