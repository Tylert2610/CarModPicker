import React from 'react';
import { Link } from 'react-router-dom';
import {
  carFullDisplayName,
  carGenerationDisplayName,
  formatCarYearRange,
} from '../../utils/carUtils';
import type { CarGenerationRead } from '../../types/Api';
import { Card } from '../ui/card';
import CardInfoItem from '../ui/card-info-item';

interface CarListItemProps {
  car: CarGenerationRead;
}

/** A car as a compact row linking to its detail page. */
const CarListItem: React.FC<CarListItemProps> = ({ car }) => {
  return (
    <Link
      to={`/car-generations/${car.id}`}
      className="block hover:no-underline h-full"
    >
      <Card className="flex flex-col h-full hover:border-info border-2 border-transparent transition-colors">
        <div className="flex-grow flex flex-col">
          <h3 className="text-lg font-semibold text-info mb-2">
            {carFullDisplayName(car)}
          </h3>
          <div className="grid grid-cols-1 gap-1 text-xs flex-grow">
            <CardInfoItem label="Generation">
              <p>{carGenerationDisplayName(car)}</p>
            </CardInfoItem>
            <CardInfoItem label="Year Range">
              <p>{formatCarYearRange(car.start_year, car.end_year)}</p>
            </CardInfoItem>
          </div>
        </div>
      </Card>
    </Link>
  );
};

export default CarListItem;
