interface ChipProps {
  label: string;
  selected?: boolean;
  onClick?: () => void;
  variant?: 'default' | 'color';
  color?: string;
}

export function Chip({ label, selected = false, onClick, variant = 'default', color }: ChipProps) {
  if (variant === 'color' && color) {
    return (
      <button
        onClick={onClick}
        className={`flex flex-col items-center gap-1 p-2 rounded-lg border-2 transition-all hover:scale-105 ${
          selected ? 'border-orange-600 shadow-lg' : 'border-gray-200 hover:border-gray-300'
        }`}
      >
        <div
          className="w-12 h-12 rounded-md shadow-sm"
          style={{ backgroundColor: color }}
        />
        <span className="text-xs font-medium text-gray-700">{label}</span>
      </button>
    );
  }

  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-full font-medium text-sm transition-all hover:scale-105 ${
        selected
          ? 'bg-orange-600 text-white shadow-md'
          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
      }`}
    >
      {label}
    </button>
  );
}
