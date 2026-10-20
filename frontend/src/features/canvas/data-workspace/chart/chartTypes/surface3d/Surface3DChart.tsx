/**
 * Surface3D Chart - 3D surface from X, Y, Z fields
 * 
 * Like 3D Scatter but creates a connected surface through the points
 * using Delaunay triangulation (mesh3d).
 */

import { ChartTypeDefinition } from '../types';
import { ColorScale, COLOR_SCALES } from '../heatmap/HeatmapChart';

export interface Surface3DChartOptions {
  // Field mappings
  xField: string;
  yField: string;
  zField: string;
  // Color settings
  colorScale: ColorScale;
  reverseScale: boolean;
  // Surface appearance
  opacity: number;
  showColorbar: boolean;
}

export { COLOR_SCALES };

export const Surface3DChart: ChartTypeDefinition<Surface3DChartOptions> = {
  id: 'surface3d',
  name: '3D Surface',
  description: 'Surface from X, Y, Z points',
  icon: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2 20L12 4l10 16" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l8-8 8 8" opacity="0.5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 12l6-4 6 4" opacity="0.3" />
    </svg>
  ),
  
  defaultOptions: {
    xField: '',
    yField: '',
    zField: '',
    colorScale: 'Viridis',
    reverseScale: false,
    opacity: 0.9,
    showColorbar: true,
  },
  
  buildTraces: (data, _xAxis, _ySeries, options) => {
    // Use explicit field mapping or fall back to chart config
    const xField = options.xField || _xAxis;
    const yField = options.yField || _ySeries[0]?.field;
    const zField = options.zField || _ySeries[1]?.field || _ySeries[0]?.field;
    
    if (!xField || !yField || !zField) {
      console.error('[Surface3D] Need X, Y, Z fields', { xField, yField, zField });
      return [];
    }
    
    // Collect raw values
    const xRaw: number[] = [];
    const yRaw: number[] = [];
    const zRaw: number[] = [];
    
    data.forEach((row, idx) => {
      const xVal = row[xField];
      const yVal = row[yField];
      const zVal = row[zField];
      
      // Parse to numbers
      const x = typeof xVal === 'number' ? xVal : (typeof xVal === 'string' && xVal.match(/^\d{4}-\d{2}/) ? idx : parseFloat(String(xVal)));
      const y = typeof yVal === 'number' ? yVal : parseFloat(String(yVal));
      const z = typeof zVal === 'number' ? zVal : parseFloat(String(zVal));
      
      if (!isNaN(x) && !isNaN(y) && !isNaN(z)) {
        xRaw.push(x);
        yRaw.push(y);
        zRaw.push(z);
      }
    });
    
    if (xRaw.length < 3) {
      console.error('[Surface3D] Need at least 3 valid points', { count: xRaw.length });
      return [];
    }
    
    // Sample data if too large (interpolation is O(n * gridSize^2))
    const MAX_SURFACE_POINTS = 1000;
    let xPoints = xRaw;
    let yPoints = yRaw;
    let zPoints = zRaw;
    
    if (xRaw.length > MAX_SURFACE_POINTS) {
      console.warn(`[Surface3D] Sampling data: ${xRaw.length.toLocaleString()} → ${MAX_SURFACE_POINTS.toLocaleString()} points`);
      const step = Math.ceil(xRaw.length / MAX_SURFACE_POINTS);
      xPoints = xRaw.filter((_, i) => i % step === 0);
      yPoints = yRaw.filter((_, i) => i % step === 0);
      zPoints = zRaw.filter((_, i) => i % step === 0);
    }
    
    // Normalize to 0-1 range
    const normalize = (arr: number[]) => {
      const min = Math.min(...arr);
      const max = Math.max(...arr);
      const range = max - min || 1;
      return { normalized: arr.map(v => (v - min) / range), min, max, range };
    };
    
    const xN = normalize(xPoints);
    const yN = normalize(yPoints);
    const zN = normalize(zPoints);
    
    // Create a dense grid and interpolate Z values using inverse distance weighting
    const gridSize = 50; // 50x50 grid = 2500 points
    const gridX: number[] = [];
    const gridY: number[] = [];
    const gridZ: number[] = [];
    const gridIntensity: number[] = [];
    
    for (let i = 0; i <= gridSize; i++) {
      for (let j = 0; j <= gridSize; j++) {
        const gx = i / gridSize;
        const gy = j / gridSize;
        
        // Inverse distance weighting interpolation
        let sumWeightedZ = 0;
        let sumWeights = 0;
        let sumWeightedIntensity = 0;
        
        for (let k = 0; k < xN.normalized.length; k++) {
          const dx = gx - xN.normalized[k];
          const dy = gy - yN.normalized[k];
          const dist = Math.sqrt(dx * dx + dy * dy);
          
          if (dist < 0.001) {
            // Very close to a data point, use its value directly
            sumWeightedZ = zN.normalized[k];
            sumWeights = 1;
            sumWeightedIntensity = zPoints[k];
            break;
          }
          
          const weight = 1 / (dist * dist); // Inverse square distance
          sumWeightedZ += weight * zN.normalized[k];
          sumWeightedIntensity += weight * zPoints[k];
          sumWeights += weight;
        }
        
        gridX.push(gx);
        gridY.push(gy);
        gridZ.push(sumWeightedZ / sumWeights);
        gridIntensity.push(sumWeightedIntensity / sumWeights);
      }
    }
    
    // mesh3d with Delaunay triangulation on the dense grid
    const trace: any = {
      type: 'mesh3d',
      x: gridX,
      y: gridY,
      z: gridZ,
      intensity: gridIntensity,
      colorscale: options.colorScale,
      reversescale: options.reverseScale,
      opacity: options.opacity,
      showscale: options.showColorbar,
      alphahull: 0, // Delaunay triangulation
      hoverinfo: 'z',
      lighting: {
        ambient: 0.7,
        diffuse: 1.0,
        specular: 0.3,
        roughness: 0.4,
        fresnel: 0.2,
      },
      lightposition: { x: 1000, y: 1000, z: 500 },
      colorbar: {
        title: zField,
        thickness: 15,
        len: 0.5,
      },
    };

    return [trace];
  },
  
  customizeLayout: (baseLayout, options) => {
    return {
      ...baseLayout,
      scene: {
        xaxis: {
          title: { text: options.xField || 'X' },
          showgrid: true,
          gridcolor: '#e2e8f0',
        },
        yaxis: {
          title: { text: options.yField || 'Y' },
          showgrid: true,
          gridcolor: '#e2e8f0',
        },
        zaxis: {
          title: { text: options.zField || 'Z' },
          showgrid: true,
          gridcolor: '#e2e8f0',
        },
        camera: {
          eye: { x: 1.5, y: 1.5, z: 1.2 },
        },
        aspectmode: 'cube' as const,
      },
      margin: { l: 0, r: 0, t: 30, b: 0 },
    };
  },
};

