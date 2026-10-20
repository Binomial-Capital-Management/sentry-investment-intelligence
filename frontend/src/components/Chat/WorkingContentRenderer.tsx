import React, { useMemo } from 'react';
import { Streamdown } from 'streamdown';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import MermaidRenderer, { isMermaidCode } from './MermaidRenderer';

interface ContentRendererProps {
  content: string;
  className?: string;
  isStreaming?: boolean;
  onLocalFileLinkClick?: (filename: string) => void;
}

const WorkingContentRenderer: React.FC<ContentRendererProps> = ({
  content,
  className = '',
  isStreaming = false,
  onLocalFileLinkClick,
}) => {
  // Memoize the processed content to prevent unnecessary re-renders
  const processedContent = useMemo(() => {
    let processed = content || '';

    // 1. Remove sandbox file links that should be handled by CodeExecutionDisplay
    processed = processed.replace(
      /\[([^\]]+\.(?:png|jpg|jpeg|gif|csv|json|txt|pdf|xlsx?|py|js|html|css))\]\(sandbox:\/mnt\/data\/[^)]+\)/gi,
      '',
    );

    // 2. Pre-process to escape monetary values (e.g. $100) to prevent them from being interpreted as LaTeX start delimiters
    // This is a heuristic: $ followed by a digit is likely currency.
    processed = processed.replace(/\$(?=\d)/g, '\\$');

    // 3. Normalize LaTeX delimiters

    // Fix generic $ ... $ LaTeX to ensure no inner spaces (which breaks remark-math)
    // We match $...$ where ... doesn't start/end with space, but if it does, we trim it.
    // Negative lookahead/behind is tricky in JS regex for "not escaped", so we capture the prefix.
    processed = processed.replace(/([^\\]|^)\$([^\$\n]+?)\$([^\\]|$)/g, (match, prefix, content, suffix) => {
      // If content is empty or just whitespace, ignore
      if (!content.trim()) return match;
      // If it looks like a currency range like $10-$20, ignore (though step 2 catches most)
      if (content.match(/^\d+-\d+$/)) return match;

      return `${prefix}$${content.trim()}$${suffix}`;
    });

    // Block math: \[ ... \] or \\[ ... \\] -> $$ ... $$
    processed = processed.replace(/(\\{0,2})\\\[([\s\S]*?)(\\{0,2})\\\]/g, (match, startSlash, content) => {
      return `\n$$${content.trim()}$$\n`;
    });

    // Inline math: \( ... \) or \\( ... \\) -> $ ... $
    processed = processed.replace(/(\\{0,2})\\\(([\s\S]*?)(\\{0,2})\\\)/g, (match, startSlash, content) => {
      return `$${content.trim()}$`;
    });

    // 4. Normalize common math environments if they aren't already wrapped
    const mathEnvs = ['equation', 'align', 'alignat', 'gather', 'matrix', 'pmatrix', 'bmatrix', 'vmatrix', 'Vmatrix'];
    mathEnvs.forEach(env => {
       const re = new RegExp(`(\\\\begin\\{${env}\\*?\\}[\\s\\S]*?\\\\end\\{${env}\\*?\\})`, 'g');
       processed = processed.replace(re, (match, p1, offset, string) => {
           // If already preceded by $ or $$, don't wrap.
           const prefix = string.substring(Math.max(0, offset - 2), offset);
           if (prefix.endsWith('$')) return match;

           return `\n$$${match}$$\n`;
       });
    });

    // 5. Clean up orphaned bullets
    processed = processed.replace(/^[\s]*-[\s]*$/gm, '');

    return processed;
  }, [content]);

  // Custom typography components
  const CustomStrong = ({ children }: any) => (
    <strong className="font-bold text-gray-900 dark:text-gray-100">{children}</strong>
  );

  const CustomH1 = ({ children }: any) => (
    <h1 className="text-3xl font-semibold mt-6 mb-3 text-gray-900 dark:text-gray-100">{children}</h1>
  );

  const CustomH2 = ({ children }: any) => (
    <h2 className="text-2xl font-semibold mt-5 mb-2.5 text-gray-900 dark:text-gray-100">{children}</h2>
  );

  const CustomH3 = ({ children }: any) => (
    <h3 className="text-xl font-semibold mt-4 mb-2 text-gray-900 dark:text-gray-100">{children}</h3>
  );

  const CustomParagraph = ({ children }: any) => (
    <p className="my-4 leading-relaxed">{children}</p>
  );

  const CustomUL = ({ children }: any) => (
    <ul className="my-5 pl-8 space-y-2">{children}</ul>
  );

  const CustomOL = ({ children }: any) => (
    <ol className="my-5 pl-8 space-y-2">{children}</ol>
  );

  const CustomBlockquote = ({ children }: any) => (
    <blockquote className="border-l-4 border-blue-500 pl-4 my-4 italic text-gray-600 dark:text-gray-400">
      {children}
    </blockquote>
  );

  // Custom code block handler for Mermaid diagrams
  const CustomCode = ({ node, inline, className, children, ...props }: any) => {
    const match = /language-(\w+)/.exec(className || '');
    const language = match ? match[1] : '';
    const codeContent = String(children).replace(/\n$/, '');

    // Check if this is a mermaid code block
    if (!inline && (language === 'mermaid' || isMermaidCode(codeContent))) {
      // Pass isStreaming to allow MermaidRenderer to wait for complete content
      return <MermaidRenderer isStreaming={isStreaming}>{codeContent}</MermaidRenderer>;
    }

    // For inline code or other languages, render normally
    if (inline) {
      return (
        <code className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-sm font-mono" {...props}>
          {children}
        </code>
      );
    }

    // Default code block (handled by Streamdown's controls)
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  };

  const CustomLink = ({ href, children, ...props }: any) => {
    const isSandbox = typeof href === 'string' && /^sandbox:\/\/|^sandbox:\/|^sandbox:/i.test(href);
    const isBareFile = typeof href === 'string' && !href.startsWith('http') && /\.(png|jpe?g|gif|webp|svg|csv|xlsx?|pdf|json|txt)$/i.test(href);
    const isTextFragment = typeof href === 'string' && (href.startsWith('#') || href.includes(':~:text='));

    if ((isSandbox || isBareFile || isTextFragment) && typeof href === 'string' && onLocalFileLinkClick) {
      let filename = '';
      try {
        if (isSandbox || isBareFile) {
          const raw = href.replace(/^sandbox:\/\//i, '').replace(/^sandbox:\//i, '').replace(/^sandbox:/i, '');
          const parts = raw.split('/');
          filename = parts[parts.length - 1] || raw;
        } else if (isTextFragment) {
          const decoded = decodeURIComponent(href);
          const m = decoded.match(/[A-Za-z0-9._-]+\.(png|jpe?g|gif|webp|svg|csv|xlsx?|json|pdf|txt)/i);
          filename = m?.[0] || '';
        }
      } catch (error) {
        console.error('Failed to parse file link:', error);
      }

      if (filename) {
        return (
          <a
            href="#"
            className="text-blue-600 dark:text-blue-400 hover:underline"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              queueMicrotask(() => onLocalFileLinkClick(filename));
            }}
            {...props}
          >
            {children}
          </a>
        );
      }
    }

    return (
      <a
        href={href}
        className="text-blue-600 dark:text-blue-400 hover:underline"
        target="_blank"
        rel="noopener noreferrer"
        {...props}
      >
        {children}
      </a>
    );
  };

  const clipboardSupported = useMemo(() => {
    if (typeof navigator === 'undefined') {
      return false;
    }
    return typeof navigator.clipboard?.writeText === 'function';
  }, []);

  const renderedContent = useMemo(() => {
    const enableControls = clipboardSupported;
    const rehypePluginsVal = [[rehypeKatex, { strict: false, trust: true }]] as any;

    try {
      return (
        <Streamdown
          parseIncompleteMarkdown={isStreaming}
          controls={enableControls}
          remarkPlugins={[remarkMath, remarkGfm]}
          rehypePlugins={rehypePluginsVal}
          components={{
            a: CustomLink,
            strong: CustomStrong,
            b: CustomStrong,
            h1: CustomH1,
            h2: CustomH2,
            h3: CustomH3,
            p: CustomParagraph,
            ul: CustomUL,
            ol: CustomOL,
            blockquote: CustomBlockquote,
            code: CustomCode,
          }}
        >
          {processedContent}
        </Streamdown>
      );
    } catch (error) {
      console.error('[WorkingContentRenderer] Falling back to react-markdown due to error:', error);
      return (
        <ReactMarkdown
          remarkPlugins={[remarkMath, remarkGfm]}
          rehypePlugins={rehypePluginsVal}
          components={{
            a: ({ node, ...props }) => <CustomLink {...props} />,
            strong: ({ node, ...props }) => <CustomStrong {...props} />,
            b: ({ node, ...props }) => <CustomStrong {...props} />,
            h1: ({ node, ...props }) => <CustomH1 {...props} />,
            h2: ({ node, ...props }) => <CustomH2 {...props} />,
            h3: ({ node, ...props }) => <CustomH3 {...props} />,
            p: ({ node, ...props }) => <CustomParagraph {...props} />,
            ul: ({ node, ...props }) => <CustomUL {...props} />,
            ol: ({ node, ...props }) => <CustomOL {...props} />,
            blockquote: ({ node, ...props }) => <CustomBlockquote {...props} />,
            code: (props) => <CustomCode {...props} />,
          }}
        >
          {processedContent}
        </ReactMarkdown>
      );
    }
  }, [clipboardSupported, processedContent, isStreaming, CustomLink]);

  const containerClass = [
    'chatgpt-content',
    className,
    isStreaming ? 'chatgpt-content--streaming' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={containerClass}>
      {renderedContent}
    </div>
  );
};

export default React.memo(WorkingContentRenderer);
