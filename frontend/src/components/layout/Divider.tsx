import React from 'react';

interface DividerProps {
  className?: string;
}

/** A horizontal rule with the app's spacing and colour. */
const Divider: React.FC<DividerProps> = ({ className = '' }) => {
  return <hr className={`border-gray-600 my-4 ${className}`} />;
};

export default Divider;
