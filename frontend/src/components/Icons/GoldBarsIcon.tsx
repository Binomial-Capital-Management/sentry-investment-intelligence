import React from 'react';

interface GoldBarsIconProps {
  size?: number;
  className?: string;
  color?: string;
  style?: React.CSSProperties;
}

const GoldBarsIcon: React.FC<GoldBarsIconProps> = ({ 
  size = 18, 
  className = '', 
  color = 'currentColor',
  style = {}
}) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    style={style}
  >
    {/* Bottom gold bar (largest) */}
    <path
      d="M2 18L4 14H20L22 18H2Z"
      stroke={color}
      strokeWidth="1.5"
      strokeLinejoin="round"
      fill="none"
    />
    {/* Middle gold bar */}
    <path
      d="M5 14L6.5 11H17.5L19 14H5Z"
      stroke={color}
      strokeWidth="1.5"
      strokeLinejoin="round"
      fill="none"
    />
    {/* Top gold bar (smallest) */}
    <path
      d="M8 11L9.5 8H14.5L16 11H8Z"
      stroke={color}
      strokeWidth="1.5"
      strokeLinejoin="round"
      fill="none"
    />
    {/* Shine line on top bar */}
    <line
      x1="10.5"
      y1="9"
      x2="13.5"
      y2="9"
      stroke={color}
      strokeWidth="1"
      strokeLinecap="round"
      opacity="0.6"
    />
  </svg>
);

export default GoldBarsIcon;
