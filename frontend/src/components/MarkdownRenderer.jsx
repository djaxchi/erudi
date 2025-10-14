import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Renders markdown safely with GitHub-flavored features (tables, lists, code blocks)
// Tailwind Typography is used for nice defaults on dark backgrounds
export default function MarkdownRenderer({ content }) {
  return (
    <div className="prose prose-invert max-w-none whitespace-normal">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        // Do not allow raw HTML for safety in LLM outputs
        skipHtml
        components={{
          code({ node, inline, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            if (inline) {
              return (
                <code className="px-1 py-0.5 rounded bg-neutral-800 text-emerald-200" {...props}>
                  {children}
                </code>
              );
            }
            return (
              <pre className="p-3 rounded bg-neutral-900 overflow-x-auto">
                <code className={match ? `language-${match[1]}` : undefined} {...props}>
                  {children}
                </code>
              </pre>
            );
          },
          a({ children, ...props }) {
            return (
              <a className="text-emerald-300 underline hover:text-emerald-200" target="_blank" rel="noreferrer" {...props}>
                {children}
              </a>
            );
          },
          table({ children }) {
            return (
              <div className="overflow-x-auto">
                <table className="table-auto w-full border-collapse border border-neutral-700">
                  {children}
                </table>
              </div>
            );
          },
          th({ children }) {
            return <th className="border border-neutral-700 bg-neutral-800 px-2 py-1 text-left">{children}</th>;
          },
          td({ children }) {
            return <td className="border border-neutral-700 px-2 py-1">{children}</td>;
          },
          ul({ children }) {
            return <ul className="list-disc pl-6">{children}</ul>;
          },
          ol({ children }) {
            return <ol className="list-decimal pl-6">{children}</ol>;
          },
        }}
      >
        {content || ""}
      </ReactMarkdown>
    </div>
  );
}
