import { ReactNode, CSSProperties } from 'react';
import { motion, MotionProps } from 'framer-motion';

// Typography variant types
type HeadingLevel = 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
type TextVariant = 'body' | 'body-sm' | 'caption' | 'overline' | 'lead';
type CodeVariant = 'inline' | 'block';

// Base typography props
interface TypographyBaseProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  color?: 'primary' | 'secondary' | 'muted' | 'accent' | 'success' | 'warning' | 'danger';
  align?: 'left' | 'center' | 'right' | 'justify';
  weight?: 'regular' | 'medium' | 'semibold' | 'bold';
  truncate?: boolean;
  animate?: boolean;
}

// Component-specific props
interface HeadingProps extends TypographyBaseProps {
  level?: HeadingLevel;
  gradient?: boolean;
}

interface TextProps extends TypographyBaseProps {
  variant?: TextVariant;
  mono?: boolean;
}

interface CodeProps extends TypographyBaseProps {
  variant?: CodeVariant;
  language?: string;
  copyable?: boolean;
}

interface LabelProps extends TypographyBaseProps {
  required?: boolean;
  htmlFor?: string;
}

// Color mapping utility
const getColor = (color?: TypographyBaseProps['color']): string => {
  const colorMap = {
    primary: 'var(--text-primary)',
    secondary: 'var(--text-secondary)',
    muted: 'var(--text-muted)',
    accent: 'var(--accent)',
    success: 'var(--success)',
    warning: 'var(--warning)',
    danger: 'var(--danger)',
  };
  return color ? colorMap[color] : 'inherit';
};

// Weight mapping utility
const getFontWeight = (weight?: TypographyBaseProps['weight']): string => {
  const weightMap = {
    regular: 'var(--fw-regular)',
    medium: 'var(--fw-medium)',
    semibold: 'var(--fw-semibold)',
    bold: 'var(--fw-bold)',
  };
  return weight ? weightMap[weight] : 'inherit';
};

// Heading Component
export const Heading = ({
  level = 'h2',
  children,
  className = '',
  style = {},
  color = 'primary',
  align = 'left',
  weight,
  gradient = false,
  truncate = false,
  animate = false,
}: HeadingProps) => {
  const Component: any = animate ? (motion as any)[level] : (level as any);

  const headingStyles: Record<HeadingLevel, CSSProperties> = {
    h1: { fontSize: 'var(--fs-32)', lineHeight: 'var(--lh-32)', fontWeight: weight || 'var(--fw-bold)' },
    h2: { fontSize: 'var(--fs-24)', lineHeight: 'var(--lh-24)', fontWeight: weight || 'var(--fw-semibold)' },
    h3: { fontSize: 'var(--fs-18)', lineHeight: 'var(--lh-18)', fontWeight: weight || 'var(--fw-semibold)' },
    h4: { fontSize: 'var(--fs-16)', lineHeight: 'var(--lh-16)', fontWeight: weight || 'var(--fw-medium)' },
    h5: { fontSize: 'var(--fs-14)', lineHeight: 'var(--lh-14)', fontWeight: weight || 'var(--fw-medium)' },
    h6: { fontSize: 'var(--fs-13)', lineHeight: 'var(--lh-13)', fontWeight: weight || 'var(--fw-medium)' },
  };

  const combinedStyle: CSSProperties = {
    ...headingStyles[level],
    color: gradient
      ? undefined
      : getColor(color),
    textAlign: align,
    fontWeight: getFontWeight(weight) || headingStyles[level].fontWeight,
    margin: 0,
    ...(truncate && {
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
    }),
    ...(gradient && {
      background: 'linear-gradient(135deg, var(--accent), color-mix(in oklab, var(--accent), white 30%))',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      backgroundClip: 'text',
    }),
    ...style,
  };

  const animationProps: Partial<MotionProps> = animate ? {
    initial: { opacity: 0, y: -10 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.3 },
  } : {};

  return (
    <Component
      className={`typography-heading ${className}`}
      style={combinedStyle as any}
      {...(animationProps as any)}
    >
      {children}
    </Component>
  );
};

// Text Component
export const Text = ({
  variant = 'body',
  children,
  className = '',
  style = {},
  color = 'primary',
  align = 'left',
  weight,
  mono = false,
  truncate = false,
  animate = false,
}: TextProps) => {
  const Component: any = animate ? (motion as any).p : 'p';

  const variantStyles: Record<TextVariant, CSSProperties> = {
    body: { fontSize: 'var(--fs-14)', lineHeight: 'var(--lh-14)' },
    'body-sm': { fontSize: 'var(--fs-13)', lineHeight: 'var(--lh-13)' },
    caption: { fontSize: 'var(--fs-12)', lineHeight: 'var(--lh-12)' },
    overline: {
      fontSize: 'var(--fs-11)',
      lineHeight: 'var(--lh-11)',
      letterSpacing: '0.05em',
    },
    lead: { fontSize: 'var(--fs-16)', lineHeight: 'var(--lh-16)' },
  };

  const combinedStyle: CSSProperties = {
    ...variantStyles[variant],
    color: getColor(color),
    textAlign: align,
    fontWeight: getFontWeight(weight),
    fontFamily: mono ? 'var(--font-mono)' : 'var(--font-sans)',
    margin: 0,
    ...(truncate && {
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
    }),
    ...style,
  };

  const animationProps: Partial<MotionProps> = animate ? {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    transition: { duration: 0.3 },
  } : {};

  return (
    <Component
      className={`typography-text ${className}`}
      style={combinedStyle as any}
      {...(animationProps as any)}
    >
      {children}
    </Component>
  );
};

// Code Component
export const Code = ({
  variant = 'inline',
  children,
  className = '',
  style = {},
  color = 'primary',
  language,
  copyable = false,
  animate = false,
}: CodeProps) => {
  const handleCopy = () => {
    if (typeof children === 'string') {
      navigator.clipboard.writeText(children);
    }
  };

  const baseStyle: CSSProperties = {
    fontFamily: 'var(--font-mono)',
    fontSize: variant === 'inline' ? '0.9em' : 'var(--fs-12)',
    color: getColor(color),
  };

  const inlineStyle: CSSProperties = {
    ...baseStyle,
    padding: '2px 6px',
    borderRadius: 'var(--radius-base)',
    background: 'color-mix(in oklab, var(--bg-subtle), white 6%)',
    display: 'inline',
  };

  const blockStyle: CSSProperties = {
    ...baseStyle,
    padding: '12px 16px',
    borderRadius: 'var(--radius-md)',
    background: 'color-mix(in oklab, var(--bg-subtle), white 3%)',
    boxShadow: '0 0 0 1px var(--border-default) inset',
    display: 'block',
    overflowX: 'auto',
    position: 'relative' as const,
    lineHeight: 'var(--lh-12)',
  };

  const Component: any = variant === 'inline'
    ? animate ? (motion as any).code : 'code'
    : animate ? (motion as any).pre : 'pre';

  const combinedStyle = variant === 'inline'
    ? { ...inlineStyle, ...style }
    : { ...blockStyle, ...style };

  const animationProps: Partial<MotionProps> = animate ? {
    initial: { opacity: 0, scale: 0.95 },
    animate: { opacity: 1, scale: 1 },
    transition: { duration: 0.2 },
  } : {};

  return (
    <Component
      className={`typography-code ${className}`}
      style={combinedStyle as any}
      {...(animationProps as any)}
    >
      {variant === 'block' && language && (
        <span style={{
          position: 'absolute',
          top: '4px',
          right: '8px',
          fontSize: 'var(--fs-11)',
          color: 'var(--text-muted)',
          letterSpacing: '0.05em',
        }}>
          {language}
        </span>
      )}
      {variant === 'block' && copyable && (
        <button
          onClick={handleCopy}
          style={{
            position: 'absolute',
            top: '8px',
            right: language ? '60px' : '8px',
            padding: '4px 8px',
            borderRadius: 'var(--radius-base)',
            background: 'color-mix(in oklab, var(--bg-subtle), white 6%)',
            border: 'none',
            color: 'var(--text-secondary)',
            fontSize: 'var(--fs-11)',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'color-mix(in oklab, var(--bg-subtle), white 10%)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'color-mix(in oklab, var(--bg-subtle), white 6%)';
          }}
        >
          Copy
        </button>
      )}
      {variant === 'block' ? <code>{children}</code> : children}
    </Component>
  );
};

// Label Component
export const Label = ({
  children,
  className = '',
  style = {},
  color = 'secondary',
  weight = 'medium',
  required = false,
  htmlFor,
  animate = false,
}: LabelProps) => {
  const Component = animate ? motion.label : 'label';

  const combinedStyle: CSSProperties = {
    fontSize: 'var(--fs-12)',
    lineHeight: 'var(--lh-12)',
    color: getColor(color),
    fontWeight: getFontWeight(weight),
    display: 'inline-block',
    marginBottom: '4px',
    ...style,
  };

  const animationProps: Partial<MotionProps> = animate ? {
    initial: { opacity: 0, x: -5 },
    animate: { opacity: 1, x: 0 },
    transition: { duration: 0.2 },
  } : {};

  return (
    <Component
      className={`typography-label ${className}`}
      style={combinedStyle as any}
      htmlFor={htmlFor}
      {...(animationProps as any)}
    >
      {children}
      {required && (
        <span style={{ color: 'var(--danger)', marginLeft: '4px' }}>*</span>
      )}
    </Component>
  );
};

// Composite Typography Component with all variants
const Typography = {
  Heading,
  Text,
  Code,
  Label,
};

export default Typography;
