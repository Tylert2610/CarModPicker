import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  variant?: 'default' | 'glass' | 'elevated';
  padding?: 'none' | 'sm' | 'md' | 'lg';
  onClick?: () => void;
  interactive?: boolean;
  style?: React.CSSProperties;
}

const Card: React.FC<CardProps> = ({
  children,
  className = '',
  variant = 'default',
  padding = 'md',
  onClick,
  interactive = false,
  style
}) => {
  const baseClasses = 'transition-all duration-300 ease-out relative overflow-hidden';
  
  const variantClasses = {
    default: 'card',
    glass: 'glass-card',
    elevated: 'bg-white/10 backdrop-blur-xl border border-white/20 shadow-2xl'
  };
  
  const paddingClasses = {
    none: '',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8'
  };
  
  const interactiveClasses = interactive ? 'cursor-pointer hover:scale-105' : '';
  
  const classes = `${baseClasses} ${variantClasses[variant]} ${paddingClasses[padding]} ${interactiveClasses} ${className}`;

  return (
    <div className={classes} onClick={onClick} style={style}>
      {/* Animated border effect */}
      <div className="absolute inset-0 rounded-inherit bg-gradient-to-r from-transparent via-white/5 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100"></div>
      
      {/* Content */}
      <div className="relative z-10">
        {children}
      </div>
      
      {/* Hover glow effect */}
      {interactive && (
        <div className="absolute inset-0 rounded-inherit bg-gradient-to-r from-primary-500/20 via-transparent to-primary-500/20 opacity-0 transition-opacity duration-300 hover:opacity-100 pointer-events-none"></div>
      )}
    </div>
  );
};

export default Card;
