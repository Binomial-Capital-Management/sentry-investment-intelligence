import React from 'react';

interface MemoryIconProps {
  size?: number;
  className?: string;
  color?: string;
}

const MemoryIcon: React.FC<MemoryIconProps> = ({ 
  size = 18, 
  className = '', 
  color = 'currentColor' 
}) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
  >
    {/* Notebook body */}
    <rect
      x="4"
      y="3"
      width="16"
      height="18"
      rx="2"
      stroke={color}
      strokeWidth="1.5"
      fill="none"
    />
    {/* Spine/binding */}
    <line
      x1="8"
      y1="3"
      x2="8"
      y2="21"
      stroke={color}
      strokeWidth="1.5"
    />
    {/* Lines on page */}
    <line
      x1="11"
      y1="8"
      x2="17"
      y2="8"
      stroke={color}
      strokeWidth="1.5"
      strokeLinecap="round"
    />
    <line
      x1="11"
      y1="12"
      x2="17"
      y2="12"
      stroke={color}
      strokeWidth="1.5"
      strokeLinecap="round"
    />
    <line
      x1="11"
      y1="16"
      x2="15"
      y2="16"
      stroke={color}
      strokeWidth="1.5"
      strokeLinecap="round"
    />
    {/* Bookmark ribbon */}
    <path
      d="M14 3V6.5L15.5 5.5L17 6.5V3"
      stroke={color}
      strokeWidth="1.5"
      strokeLinejoin="round"
      fill="none"
    />
  </svg>
);

export default MemoryIcon;

