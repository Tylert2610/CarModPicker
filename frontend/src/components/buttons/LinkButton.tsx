import React from 'react';
import { Link, type LinkProps } from 'react-router-dom';

interface LinkButtonProps extends Omit<LinkProps, 'className'> {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const LinkButton: React.FC<LinkButtonProps> = ({ 
  children, 
  to, 
  variant = 'primary',
  size = 'md',
  className = '',
  ...props 
}) => {
  const baseClasses = "inline-flex items-center justify-center font-semibold rounded-xl transition-all duration-300 transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500";
  
  const variantClasses = {
    primary: "btn-primary",
    secondary: "btn-secondary",
    outline: "glass-button border-2 border-primary-500 text-primary-400 hover:bg-primary-500 hover:text-white"
  };
  
  const sizeClasses = {
    sm: "px-4 py-2 text-sm",
    md: "px-6 py-3 text-base",
    lg: "px-8 py-4 text-lg"
  };

  const classes = `${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`;

  return (
    <Link
      to={to}
      className={classes}
      {...props}
    >
      {children}
    </Link>
  );
};

export default LinkButton;
