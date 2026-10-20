import { ChevronRight, Home } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useMemo } from 'react';

interface BreadcrumbItem {
  label: string;
  path: string;
  icon?: React.ComponentType<any>;
}

export default function Breadcrumbs() {
  const location = useLocation();

  const breadcrumbs = useMemo(() => {
    const paths = location.pathname.split('/').filter(Boolean);
    const items: BreadcrumbItem[] = [
      { label: 'Home', path: '/', icon: Home },
    ];

    // Build breadcrumb trail (max 3 levels as per requirement)
    let currentPath = '';
    paths.slice(0, 2).forEach(segment => {
      currentPath += `/${segment}`;

      // Capitalize and format segment
      const label = segment
        .replace(/-/g, ' ')
        .replace(/\b\w/g, char => char.toUpperCase());

      items.push({
        label,
        path: currentPath,
      });
    });

    return items;
  }, [location.pathname]);

  // Don't show breadcrumbs on home page
  if (location.pathname === '/') return null;

  return (
    <nav className="flex items-center gap-2 text-sm text-white/60 mb-4">
      {breadcrumbs.map((item, index) => {
        const isLast = index === breadcrumbs.length - 1;
        const Icon = item.icon;

        return (
          <div key={item.path} className="flex items-center gap-2">
            {index > 0 && <ChevronRight className="w-4 h-4 text-white/30" />}

            {isLast ? (
              <span className="flex items-center gap-1 text-white">
                {Icon && <Icon className="w-4 h-4" />}
                {item.label}
              </span>
            ) : (
              <Link
                to={item.path}
                className="flex items-center gap-1 hover:text-white transition-colors"
              >
                {Icon && <Icon className="w-4 h-4" />}
                {item.label}
              </Link>
            )}
          </div>
        );
      })}
    </nav>
  );
}

// Simple breadcrumb for specific pages with custom labels
interface CustomBreadcrumbsProps {
  items: Array<{
    label: string;
    path?: string;
  }>;
}

export function CustomBreadcrumbs({ items }: CustomBreadcrumbsProps) {
  return (
    <nav className="flex items-center gap-2 text-sm text-white/60 mb-4">
      {items.map((item, index) => {
        const isLast = index === items.length - 1;

        return (
          <div key={index} className="flex items-center gap-2">
            {index > 0 && <ChevronRight className="w-4 h-4 text-white/30" />}

            {isLast || !item.path ? (
              <span className="text-white">{item.label}</span>
            ) : (
              <Link
                to={item.path}
                className="hover:text-white transition-colors"
              >
                {item.label}
              </Link>
            )}
          </div>
        );
      })}
    </nav>
  );
}
