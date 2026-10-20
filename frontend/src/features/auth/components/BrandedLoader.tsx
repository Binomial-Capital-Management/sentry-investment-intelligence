interface BrandedLoaderProps {
  subtitle?: string;
}

export function BrandedLoader({ subtitle = 'Loading...' }: BrandedLoaderProps) {
  return (
    <div
      className="flex items-center justify-center min-h-screen animate-in fade-in duration-300"
      style={{ background: 'rgba(250, 249, 248, 0.95)' }}
    >
      <div className="flex flex-col items-center gap-4">
        <div className="relative">
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-gray-200" />
          <div className="absolute top-0 left-0 animate-spin rounded-full h-16 w-16 border-4 border-transparent border-t-blue-600" />
        </div>
        <div className="flex flex-col items-center gap-1">
          <p className="text-gray-900 font-medium">Sentry Intelligence</p>
          <p className="text-gray-500 text-sm">{subtitle}</p>
        </div>
      </div>
    </div>
  );
}
