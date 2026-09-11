import React from 'react';
import { Card } from '../ui/card';

interface AddItemTileProps {
  title: string;
  description: string;
  onClick: () => void;
  className?: string;
}

/** A dashed placeholder tile that invites the user to add a new item. */
const AddItemTile: React.FC<AddItemTileProps> = ({
  title,
  description,
  onClick,
  className = '',
}) => {
  return (
    <Card
      onClick={onClick}
      className={`group cursor-pointer flex flex-col items-center justify-center text-center p-6 h-full min-h-[200px] border-2 border-dashed border-gray-700 hover:border-primary hover:bg-gray-800/60 hover:shadow-lg hover:shadow-primary/10 transition-all duration-300 ${className}`}
    >
      <div className="flex items-center justify-center w-12 h-12 rounded-full bg-primary/10 text-primary text-3xl font-light mb-4 group-hover:bg-primary/20 group-hover:scale-110 transition-all duration-300">
        +
      </div>
      <h3 className="text-2xl font-semibold text-primary mb-2 group-hover:text-primary transition-colors">
        {title}
      </h3>
      <p className="text-gray-400 text-base">{description}</p>
    </Card>
  );
};

export default AddItemTile;
