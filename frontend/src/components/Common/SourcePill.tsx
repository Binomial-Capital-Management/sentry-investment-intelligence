import type { Source } from '@/types';

interface SourcePillProps {
  source: Source;
  index: number;
}

const SourcePill = ({ source, index }: SourcePillProps) => {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-xs hover:opacity-80 transition-opacity"
      style={{
        color: '#0078D4',
        textDecoration: 'none',
        marginRight: '8px',
      }}
    >
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          minWidth: '16px',
          height: '16px',
          padding: '0 4px',
          borderRadius: '2px',
          background: '#0078D4',
          color: 'white',
          fontSize: '10px',
          fontWeight: '600',
        }}
      >
        {index + 1}
      </span>
      <span style={{ fontWeight: '500' }}>{source.title}</span>
    </a>
  );
};

export default SourcePill;
