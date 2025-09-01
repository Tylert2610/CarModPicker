import React from 'react';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  color?: 'primary' | 'white' | 'custom';
  className?: string;
  text?: string;
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  color = 'primary',
  className = '',
  text
}) => {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
    xl: 'w-12 h-12'
  };

  const colorClasses = {
    primary: 'border-primary-500/30 border-t-primary-500',
    white: 'border-white/30 border-t-white',
    custom: 'border-current/30 border-t-current'
  };

  return (
    <div className={`flex flex-col items-center justify-center ${className}`}>
      <div className="relative">
        {/* Main spinner */}
        <div 
          className={`${sizeClasses[size]} border-2 rounded-full animate-spin ${colorClasses[color]}`}
        />
        
        {/* Glow effect for larger sizes */}
        {(size === 'lg' || size === 'xl') && (
          <div 
            className={`absolute inset-0 ${sizeClasses[size]} border-2 rounded-full animate-pulse ${colorClasses[color].replace('border-t-', 'border-')}`}
            style={{ filter: 'blur(2px)' }}
          />
        )}
      </div>
      
      {/* Loading text */}
      {text && (
        <p className="mt-3 text-sm text-neutral-400 animate-pulse">
          {text}
        </p>
      )}
    </div>
  );
};

export default LoadingSpinner;
