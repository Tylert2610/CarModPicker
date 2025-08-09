import React from 'react';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
}

const PageHeader: React.FC<PageHeaderProps> = ({ title, subtitle }) => {
  return (
    <div className="mb-6">
      <h1 className="text-3xl font-bold text-white">{title}</h1>
      {subtitle && <p className="text-lg text-gray-400 mt-1">{subtitle}</p>}
    </div>
  );
};

export default PageHeader;
