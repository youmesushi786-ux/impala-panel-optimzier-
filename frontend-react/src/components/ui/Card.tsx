import { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function Card({ children, className = '', hover = false, title, subtitle, actions }: CardProps) {
  return (
    <div
      className={`bg-white rounded-xl shadow-md border border-gray-200 overflow-hidden transition-all duration-300 ${
        hover ? 'hover:shadow-xl hover:-translate-y-1' : ''
      } ${className}`}
    >
      {(title || subtitle || actions) && (
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            {title && <h3 className="text-lg font-semibold text-gray-900">{title}</h3>}
            {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
          </div>
          {actions && <div>{actions}</div>}
        </div>
      )}
      <div className="p-6">{children}</div>
    </div>
  );
}
