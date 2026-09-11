import React from 'react';

interface CardInfoItemProps {
  label: string;
  children: React.ReactNode;
  className?: string;
}

/** A labelled value pair inside a Card. */
const CardInfoItem: React.FC<CardInfoItemProps> = ({
  label = '',
  children,
  className = '',
}) => {
  return (
    <div className={className}>
      <p className="font-medium text-muted-foreground">{label}</p>
      <div className="text-foreground">{children}</div>
    </div>
  );
};

export default CardInfoItem;
