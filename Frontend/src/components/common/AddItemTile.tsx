import React from 'react';
import Card from './Card';

interface AddItemTileProps {
  title: string;
  description: string;
  onClick: () => void;
  className?: string;
  
}

const AddItemTile: React.FC<AddItemTileProps> = ({
  title,
  description,
  onClick,
  className = '',
  // icon,
}) => {
  return (
    <Card
      onClick={onClick}
      className={`cursor-pointer hover:bg-gray-800 flex flex-col items-center justify-center text-center p-6 h-full min-h-[200px] border-2 border-dashed border-gray-700 hover:border-indigo-500 transition-colors ${className}`}
    >
      
      <h3 className="text-xl font-semibold text-indigo-400 mb-2">{title}</h3>
      <p className="text-gray-400 text-sm">{description}</p>
    </Card>
  );
};

export default AddItemTile;
