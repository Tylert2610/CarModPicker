import React from 'react';
import type { BuildListRead } from '../../types/Api';
import Card from '../common/Card';
import CardInfoItem from '../common/CardInfoItem'; 
import { Link } from 'react-router-dom';

interface BuildListItemProps {
  buildList: BuildListRead;
}

const BuildListItem: React.FC<BuildListItemProps> = ({ buildList }) => {
  return (
    <Link
      to={`/build-lists/${buildList.id}`}
      className="block hover:no-underline h-full"
    >
      <Card className="flex flex-col h-full hover:border-indigo-500 border-2 border-transparent transition-colors">
        {buildList.image_url && (
          <img
            src={buildList.image_url}
            alt={buildList.name}
            className="w-full h-40 object-cover rounded-md mb-4"
          />
        )}
        <div className="flex-grow flex flex-col">
          <h3 className="text-lg font-semibold text-indigo-400 mb-2">
            {buildList.name}
          </h3>
          {buildList.description && (
            <p className="text-sm text-gray-400 mb-2 flex-grow">
              {buildList.description}
            </p>
          )}
          <div className="text-xs text-gray-500">
            <CardInfoItem label="Build List ID">
              <p>{buildList.id}</p>
            </CardInfoItem>
            <CardInfoItem label="Associated Car ID">
              <p>{buildList.car_id}</p>
            </CardInfoItem>
          </div>
        </div>
        
      </Card>
    </Link>
  );
};

export default BuildListItem;
