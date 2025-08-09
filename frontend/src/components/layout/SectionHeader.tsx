import React from 'react';

interface SectionHeaderProps {
  title: string;
  className?: string;
}

const SectionHeader: React.FC<SectionHeaderProps> = ({
  title,
  className = '',
}) => {
  return (
    <div className={`mb-4 ${className}`}>
      <h2 className="text-xl font-semibold text-white">{title}</h2>
    </div>
  );
};

export default SectionHeader;
