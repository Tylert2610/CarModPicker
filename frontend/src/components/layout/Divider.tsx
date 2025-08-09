import React from 'react';

interface DividerProps {
  className?: string;
}

const Divider: React.FC<DividerProps> = ({ className = '' }) => {
  return <hr className={`border-gray-600 my-4 ${className}`} />;
};

export default Divider;
