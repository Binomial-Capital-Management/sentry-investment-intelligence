/**
 * StructureTypeWarning - UI warning for incompatible data structure types
 * 
 * Shows when user selects endpoints with incompatible time structures
 * (e.g., snapshot + date, fiscal + snapshot). Unlike GranularitySelector
 * which handles resolvable conflicts, this warns about unresolvable ones.
 * 
 * Color: Red (blocking error) vs GranularitySelector's amber (resolvable warning)
 */

import type { TimeStructure } from '@/utils/compatibilityMatrix';
import { getStructureLabel } from '@/utils/compatibilityMatrix';

interface StructureTypeWarningProps {
  /** Structure types detected across selected endpoints */
  structureTypesDetected: TimeStructure[];
  /** Map of structure type to endpoint names for display */
  endpointsByStructure?: Record<TimeStructure, string[]>;
  /** Pairs of incompatible structures found */
  incompatiblePairs: [TimeStructure, TimeStructure][];
}

export default function StructureTypeWarning({
  structureTypesDetected,
  endpointsByStructure,
  incompatiblePairs,
}: StructureTypeWarningProps) {
  // Don't render if no incompatibilities
  if (incompatiblePairs.length === 0) {
    return null;
  }

  // Format the incompatible pair for display
  const formatIncompatiblePair = (pair: [TimeStructure, TimeStructure]): string => {
    return `${getStructureLabel(pair[0])} + ${getStructureLabel(pair[1])}`;
  };

  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 mb-4">
      <div className="flex items-start gap-2">
        {/* X Circle Icon */}
        <svg 
          className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" 
          fill="none" 
          viewBox="0 0 24 24" 
          stroke="currentColor"
        >
          <path 
            strokeLinecap="round" 
            strokeLinejoin="round" 
            strokeWidth={2} 
            d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" 
          />
        </svg>
        
        <div className="flex-1">
          <h4 className="font-medium text-red-800">Incompatible data structures</h4>
          <p className="text-sm text-red-700 mt-1">
            These endpoints cannot be joined together:
          </p>
          
          {/* List of detected structure types with their endpoints */}
          <ul className="text-sm text-red-700 mt-2 space-y-1">
            {structureTypesDetected
              .filter(structure => structure !== 'none')
              .map((structure) => (
                <li key={structure} className="flex items-center gap-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-red-400" />
                  <span className="font-medium">{getStructureLabel(structure)}</span>
                  {endpointsByStructure?.[structure] && endpointsByStructure[structure].length > 0 && (
                    <span className="text-red-600 text-xs">
                      ({endpointsByStructure[structure].slice(0, 2).join(', ')}
                      {endpointsByStructure[structure].length > 2 && 
                        `, +${endpointsByStructure[structure].length - 2} more`})
                    </span>
                  )}
                </li>
              ))}
          </ul>
          
          {/* Show specific incompatible combinations */}
          <div className="mt-3 text-sm text-red-700">
            <span className="font-medium">Incompatible: </span>
            {incompatiblePairs.map(formatIncompatiblePair).join(', ')}
          </div>
          
          {/* Tip box */}
          <div className="mt-3 p-2 bg-red-100 rounded text-sm text-red-800">
            <strong>Tip:</strong> Add these as separate groups in your workspace, 
            or select endpoints with compatible time structures.
          </div>
        </div>
      </div>
    </div>
  );
}
