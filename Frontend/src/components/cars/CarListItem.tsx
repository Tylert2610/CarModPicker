import React from 'react';
import { Link } from 'react-router-dom';
import type { CarRead } from '../../types/Api';
import Card from '../common/Card';
import CardInfoItem from '../common/CardInfoItem';

interface CarListItemProps {
  car: CarRead;
}

const CarListItem: React.FC<CarListItemProps> = ({ car }) => {
  return (
    <Link to={`/cars/${car.id}`} className="block hover:no-underline h-full">
      <Card className="flex flex-col h-full hover:border-indigo-500 border-2 border-transparent transition-colors">
        {/* Add hover effect */}
        {car.image_url && (
          <img
            src={car.image_url}
            alt={`${car.year} ${car.make} ${car.model}`}
            className="w-full h-40 object-cover rounded-md mb-4"
          />
        )}
        <div className="flex-grow flex flex-col">
          <h3 className="text-lg font-semibold text-indigo-400 mb-2">
            {car.year} {car.make} {car.model}
          </h3>
          <div className="grid grid-cols-1 gap-1 text-xs flex-grow">
            {car.trim && (
              <CardInfoItem label="Trim">
                <p>{car.trim}</p>
              </CardInfoItem>
            )}
            {car.vin && (
              <CardInfoItem label="VIN">
                <p>{car.vin}</p>
              </CardInfoItem>
            )}
            <CardInfoItem label="Car ID">
              <p>{car.id}</p>
            </CardInfoItem>
          </div>
        </div>
      </Card>
    </Link>
  );
};

export default CarListItem;
