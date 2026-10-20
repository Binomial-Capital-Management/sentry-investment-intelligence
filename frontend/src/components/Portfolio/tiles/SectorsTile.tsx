import { useState } from 'react';
import { usePortfolioDetail } from '../mosaic/PortfolioDetailContext';

export default function SectorsTile() {
  const { sectorData, sectorColors } = usePortfolioDetail();
  const [hoveredSector, setHoveredSector] = useState<string | null>(null);

  if (sectorData.length === 0) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fff', color: '#9ca3af', fontSize: '13px' }}>
        No sector data available
      </div>
    );
  }

  const chartSize = 140;
  const cx = chartSize / 2;
  const cy = chartSize / 2;
  const outerR = 60;
  const innerR = 38;

  return (
    <div style={{ height: '100%', overflow: 'auto', background: '#fff', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px', padding: '14px 16px', flex: 1, minHeight: 0 }}>
        {/* Donut */}
        <div style={{ flexShrink: 0 }}>
          <svg width={chartSize} height={chartSize} viewBox={`0 0 ${chartSize} ${chartSize}`}>
            {(() => {
              let currentAngle = -90;
              return sectorData.map((item, index) => {
                const angle = (item.percentage / 100) * 360;
                const startAngle = currentAngle;
                const endAngle = currentAngle + angle;
                currentAngle = endAngle;

                const startRad = (startAngle * Math.PI) / 180;
                const endRad = (endAngle * Math.PI) / 180;
                const x1 = cx + outerR * Math.cos(startRad);
                const y1 = cy + outerR * Math.sin(startRad);
                const x2 = cx + outerR * Math.cos(endRad);
                const y2 = cy + outerR * Math.sin(endRad);
                const x3 = cx + innerR * Math.cos(endRad);
                const y3 = cy + innerR * Math.sin(endRad);
                const x4 = cx + innerR * Math.cos(startRad);
                const y4 = cy + innerR * Math.sin(startRad);
                const largeArc = angle > 180 ? 1 : 0;
                const d = `M ${x1} ${y1} A ${outerR} ${outerR} 0 ${largeArc} 1 ${x2} ${y2} L ${x3} ${y3} A ${innerR} ${innerR} 0 ${largeArc} 0 ${x4} ${y4} Z`;
                const color = sectorColors[item.sector] || '#9ca3af';
                const isHovered = hoveredSector === item.sector;

                return (
                  <path
                    key={index}
                    d={d}
                    fill={color}
                    opacity={hoveredSector && !isHovered ? 0.4 : 0.85}
                    stroke="#fff"
                    strokeWidth="1.5"
                    style={{ cursor: 'pointer', transition: 'opacity 0.15s' }}
                    onMouseEnter={() => setHoveredSector(item.sector)}
                    onMouseLeave={() => setHoveredSector(null)}
                  />
                );
              });
            })()}
            <text x={cx} y={cy - 6} textAnchor="middle" style={{ fontSize: '22px', fontWeight: '700', fill: '#111827' }}>
              {sectorData.length}
            </text>
            <text x={cx} y={cy + 10} textAnchor="middle" style={{ fontSize: '9px', fontWeight: '600', fill: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              sectors
            </text>
          </svg>
        </div>

        {/* Legend */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '3px', paddingTop: '4px' }}>
          {sectorData.map((item) => {
            const color = sectorColors[item.sector] || '#9ca3af';
            const isHovered = hoveredSector === item.sector;
            return (
              <div
                key={item.sector}
                onMouseEnter={() => setHoveredSector(item.sector)}
                onMouseLeave={() => setHoveredSector(null)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '3px 6px',
                  borderRadius: '4px',
                  background: isHovered ? '#f3f4f6' : 'transparent',
                  cursor: 'pointer',
                  transition: 'background 0.1s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}>
                  <div style={{ width: '8px', height: '8px', borderRadius: '2px', background: color, flexShrink: 0 }} />
                  <span style={{ fontSize: '11px', color: '#374151', fontWeight: isHovered ? '600' : '500', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {item.sector}
                  </span>
                </div>
                <span style={{ fontSize: '11px', fontWeight: '600', color: isHovered ? '#111827' : '#6b7280', fontVariantNumeric: 'tabular-nums', flexShrink: 0, marginLeft: '8px' }}>
                  {item.percentage.toFixed(1)}%
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
