import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: (event: React.MouseEvent<HTMLDivElement>) => void; // Add onClick prop
}

const Card: React.FC<CardProps> = ({
  children,
  className = '',
  onClick, // Destructure onClick
}) => {
  return (
    <div
      className={`bg-gray-900 shadow-md rounded-lg p-6 ${className}`}
      onClick={onClick} // Apply onClick to the div
    >
      {children}
    </div>
  );
};

export default Card;
