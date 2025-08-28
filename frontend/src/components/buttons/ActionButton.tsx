import React from 'react';

interface ActionButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
}

const ActionButton: React.FC<ActionButtonProps> = ({
  children,
  className = '',
  ...props
}) => {
  return (
    <button
      type="button"
      {...props}
            className={`px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-md text-sm font-medium focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 focus:ring-offset-gray-800 ${className}`}
    >
      {children}
    </button>
  );
};

export default ActionButton;
