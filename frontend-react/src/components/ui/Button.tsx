import { ReactNode, ButtonHTMLAttributes } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: 'primary' | 'secondary' | 'outline' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
}

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  className = '',
  disabled,
  ...props
}: ButtonProps) {
  const baseStyles = 'font-medium rounded-lg transition-all duration-200 flex items-center justify-center gap-2';

  const variants = {
    primary: 'bg-orange-600 hover:bg-orange-700 text-white shadow-md hover:shadow-lg active:scale-95 disabled:bg-gray-300 disabled:cursor-not-allowed',
    secondary: 'bg-gray-700 hover:bg-gray-800 text-white shadow-md hover:shadow-lg active:scale-95 disabled:bg-gray-300 disabled:cursor-not-allowed',
    outline: 'border-2 border-orange-600 text-orange-600 hover:bg-orange-50 active:scale-95 disabled:border-gray-300 disabled:text-gray-300 disabled:cursor-not-allowed',
    danger: 'bg-red-500 hover:bg-red-600 text-white shadow-md hover:shadow-lg active:scale-95 disabled:bg-gray-300 disabled:cursor-not-allowed',
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-5 py-2.5 text-base',
    lg: 'px-6 py-3 text-lg',
  };

  return (
    <button
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${fullWidth ? 'w-full' : ''} ${className}`}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}
