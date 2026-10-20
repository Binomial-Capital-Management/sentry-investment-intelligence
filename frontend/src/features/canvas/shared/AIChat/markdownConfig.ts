import { useMemo } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import type { Components } from 'react-markdown';
import { createElement } from 'react';

export function useMarkdownComponents(): Partial<Components> {
  return useMemo(() => ({
    code({ node, inline, className, children, ...props }: any) {
      const match = /language-(\w+)/.exec(className || '');
      return !inline && match ? (
        createElement('div', {
          style: {
            borderRadius: 'var(--cc-radius-sm)',
            overflow: 'hidden',
            marginBottom: '0.75rem',
          },
        },
          createElement(SyntaxHighlighter, {
            style: oneDark,
            language: match[1],
            PreTag: 'div',
            customStyle: {
              margin: 0,
              fontSize: '0.688rem',
              fontFamily: 'var(--cc-font-mono)',
              lineHeight: 1.5,
            },
            ...props,
            children: String(children).replace(/\n$/, ''),
          })
        )
      ) : (
        createElement('code', {
          style: {
            fontFamily: 'var(--cc-font-mono)',
            fontSize: '0.9em',
            padding: '0.125em 0.25em',
            borderRadius: '0.25rem',
            backgroundColor: 'hsl(var(--cc-bg-200))',
          },
          ...props,
          children,
        })
      );
    },
    p({ children }) {
      return createElement('p', {
        style: {
          marginBottom: '0.75rem',
          fontFamily: 'var(--cc-font-response)',
          fontSize: '0.875rem',
          lineHeight: 1.625,
        },
      }, children);
    },
    ul({ children }) {
      return createElement('ul', {
        style: {
          listStyleType: 'disc',
          paddingLeft: '1.25rem',
          marginBottom: '0.75rem',
        },
      }, children);
    },
    ol({ children }) {
      return createElement('ol', {
        style: {
          listStyleType: 'decimal',
          paddingLeft: '1.25rem',
          marginBottom: '0.75rem',
        },
      }, children);
    },
    li({ children }) {
      return createElement('li', {
        style: {
          marginBottom: '0.25rem',
          fontFamily: 'var(--cc-font-response)',
          fontSize: '0.875rem',
          lineHeight: 1.625,
        },
      }, children);
    },
    h1({ children }) {
      return createElement('h1', {
        style: {
          fontFamily: 'var(--cc-font-ui)',
          fontSize: '1.25rem',
          fontWeight: 600,
          marginBottom: '0.5rem',
          color: 'hsl(var(--cc-text-000))',
        },
      }, children);
    },
    h2({ children }) {
      return createElement('h2', {
        style: {
          fontFamily: 'var(--cc-font-ui)',
          fontSize: '1.125rem',
          fontWeight: 600,
          marginBottom: '0.5rem',
          color: 'hsl(var(--cc-text-000))',
        },
      }, children);
    },
    h3({ children }) {
      return createElement('h3', {
        style: {
          fontFamily: 'var(--cc-font-ui)',
          fontSize: '1rem',
          fontWeight: 600,
          marginBottom: '0.5rem',
          color: 'hsl(var(--cc-text-000))',
        },
      }, children);
    },
    strong({ children }) {
      return createElement('strong', { style: { fontWeight: 600 } }, children);
    },
    a({ href, children }) {
      return createElement('a', {
        href,
        target: '_blank',
        rel: 'noopener noreferrer',
        style: {
          color: 'hsl(var(--cc-accent-main-000))',
          textDecoration: 'none',
        },
        onMouseEnter: (e: any) => { e.currentTarget.style.textDecoration = 'underline'; },
        onMouseLeave: (e: any) => { e.currentTarget.style.textDecoration = 'none'; },
      }, children);
    },
  }), []);
}
