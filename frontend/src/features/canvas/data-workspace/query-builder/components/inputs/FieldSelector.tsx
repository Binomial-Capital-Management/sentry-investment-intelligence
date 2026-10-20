/**
 * FieldSelector - Grid for selecting fields from an endpoint
 * Extracted from SingleObjectForm lines 634-697
 */

const FONT_UI = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";

interface FieldSelectorProps {
  fields: string[];
  selectedFields: string[];
  onFieldToggle: (field: string) => void;
  onSelectAll: () => void;
}

export default function FieldSelector({
  fields,
  selectedFields,
  onFieldToggle,
  onSelectAll,
}: FieldSelectorProps) {
  return (
    <div style={{ fontFamily: FONT_UI }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <h3 style={{ fontSize: '0.688rem', fontWeight: 500, color: 'hsl(60 2.5% 23.3% / 65%)' }}>
          Select Fields ({selectedFields.length} of {fields.length})
        </h3>
        <button
          onClick={onSelectAll}
          style={{ fontSize: '0.688rem', color: 'hsl(60 2.5% 23.3% / 40%)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: FONT_UI }}
        >
          Select All
        </button>
      </div>
      <div className="grid grid-cols-2 gap-1">
        {fields.map((field) => (
          <button
            key={field}
            onClick={() => onFieldToggle(field)}
            style={{
              textAlign: 'left',
              padding: '0.375rem 0.5rem',
              fontSize: '0.688rem',
              fontFamily: FONT_UI,
              borderRadius: '0.375rem',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              border: selectedFields.includes(field)
                ? '0.5px solid hsl(30 3.3% 11.8% / 15%)'
                : '0.5px solid transparent',
              backgroundColor: selectedFields.includes(field)
                ? 'hsl(30 3.3% 11.8% / 8%)'
                : 'hsl(30 3.3% 11.8% / 3%)',
              color: selectedFields.includes(field)
                ? 'hsl(60 2.5% 23.3%)'
                : 'hsl(60 2.5% 23.3% / 40%)',
              cursor: 'pointer',
              transition: 'all 0.1s ease',
            }}
          >
            {field}
          </button>
        ))}
      </div>
    </div>
  );
}
