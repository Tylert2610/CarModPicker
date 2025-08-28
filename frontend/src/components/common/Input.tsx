import React from 'react';

interface InputProps {
  type?: string;
  placeholder?: string;
  value?: string | number;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  className?: string;
  error?: string;
  success?: boolean;
  disabled?: boolean;
  required?: boolean;
  icon?: React.ReactNode;
  iconPosition?: 'left' | 'right';
  label?: string;
  id?: string;
  name?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  variant?: string;
  helperText?: string;
  autoComplete?: string;
  ref?: React.Ref<HTMLInputElement>;
}

const Input: React.FC<InputProps> = ({
  type = 'text',
  placeholder,
  value,
  onChange,
  className = '',
  error,
  success = false,
  disabled = false,
  required = false,
  icon,
  iconPosition = 'left',
  label,
  id,
  name,
  leftIcon,
  rightIcon,
  variant,
  helperText,
  autoComplete,
  ref
}) => {
  const baseClasses = 'w-full transition-all duration-300 ease-out focus:outline-none';
  
  // Handle variant styling
  const variantClasses = variant === 'glass' 
    ? 'glass-input bg-white/5 border-white/20 backdrop-blur-sm' 
    : '';
  
  const stateClasses = error 
    ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20' 
    : success 
    ? 'border-green-500 focus:border-green-500 focus:ring-green-500/20'
    : 'border-white/20 focus:border-primary-500 focus:ring-primary-500/20';
  
  const disabledClasses = disabled ? 'opacity-50 cursor-not-allowed' : '';
  
  // Handle both old icon prop and new leftIcon/rightIcon props
  const leftIconToUse = leftIcon || (icon && iconPosition === 'left' ? icon : null);
  const rightIconToUse = rightIcon || (icon && iconPosition === 'right' ? icon : null);
  // Calculate padding classes based on icons
  let paddingClasses = '!px-5'; // Default padding with !important to override CSS
  if (leftIconToUse && rightIconToUse) {
    paddingClasses = '!pl-16 !pr-16'; // Both icons: balanced padding
  } else if (leftIconToUse) {
    paddingClasses = '!pl-16 !pr-5'; // Left icon only: left padding to avoid collision with icon
  } else if (rightIconToUse) {
    paddingClasses = '!pl-5 !pr-16'; // Right icon only: right padding to avoid collision with icon
  }

  return (
    <div className="relative">
      {/* Label */}
      {label && (
        <label htmlFor={id} className="block text-sm font-medium text-neutral-300 mb-2">
          {label}
        </label>
      )}
      
      {/* Input Container */}
      <div className="relative">
        {/* Left Icon */}
        {leftIconToUse && (
          <div className="absolute left-3 top-1/2 transform -translate-y-1/2 z-10 flex items-center justify-center w-6 h-6">
            <div className="text-white/60 flex items-center justify-center">
              {leftIconToUse}
            </div>
          </div>
        )}
        
        {/* Right Icon */}
        {rightIconToUse && (
          <div className="absolute right-3 top-1/2 transform -translate-y-1/2 z-10 flex items-center justify-center w-6 h-6">
            <div className="text-white/60 flex items-center justify-center">
              {rightIconToUse}
            </div>
          </div>
        )}
        
        {/* Input */}
        <input
          ref={ref}
          id={id}
          name={name}
          type={type}
          placeholder={placeholder}
          value={value?.toString() ?? ''}
          onChange={onChange}
          disabled={disabled}
          required={required}
          autoComplete={autoComplete}
          className={`
            ${baseClasses}
            ${variantClasses}
            ${stateClasses}
            ${disabledClasses}
            ${paddingClasses}
            input-modern
            min-h-[44px]
            ${className}
          `}
        />
      </div>
      
      {/* Helper Text */}
      {helperText && !error && (
        <div className="mt-2 text-sm text-neutral-400 animate-slideInUp">
          {helperText}
        </div>
      )}
      
      {/* Error Message */}
      {error && (
        <div className="mt-2 text-sm text-red-400 animate-slideInUp">
          {error}
        </div>
      )}
      
      {/* Success Indicator */}
      {success && !error && (
        <div className="absolute right-3 top-1/2 transform -translate-y-1/2 z-10">
          <div className="w-5 h-5 bg-green-500 rounded-full flex items-center justify-center">
            <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          </div>
        </div>
      )}
      
      {/* Animated Border */}
      <div className="absolute inset-0 rounded-xl border border-transparent pointer-events-none transition-all duration-300 group-hover:border-white/30"></div>
    </div>
  );
};

export default Input;
