import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Renders markdown safely with GitHub-flavored features (tables, lists, code blocks)
// Tailwind Typography is used for nice defaults on dark backgrounds
export default function MarkdownRenderer({ content }) {
  // Fonction pour ouvrir un lien externe via Electron (ou fallback en dev)
  const handleLinkClick = async (href) => {
  if (!href) return;

  // On attend un tick du rendu React pour laisser Electron injecter le preload
  await new Promise((r) => setTimeout(r, 0));

  const api = window?.electronAPI;

  if (api && typeof api.openExternal === "function") {
    console.log("Ouverture externe via Electron :", href);
    try {
      api.openExternal(href);
    } catch (err) {
      window.open(href, "_blank");
    }
  } else {
    // Aucun message d’erreur : fallback silencieux
    window.open(href, "_blank");
  }
};

  return (
    <div className="prose prose-invert max-w-none whitespace-normal">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        // Do not allow raw HTML for safety in LLM outputs
        skipHtml
        components={{
          code({ inline, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            if (inline) {
              return (
                <code
                  className="px-1 py-0.5 rounded bg-neutral-800 text-emerald-200"
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return (
              <pre className="p-3 rounded bg-neutral-900 overflow-x-auto">
                <code
                  className={match ? `language-${match[1]}` : undefined}
                  {...props}
                >
                  {children}
                </code>
              </pre>
            );
          },

          a({ href, children, ...props }) {
            const handleClick = (e) => {
              e.preventDefault();
              if (href) handleLinkClick(href);
            };
            return (
              <a
                href={href}
                onClick={handleClick}
                className="text-emerald-300 underline hover:text-emerald-200 cursor-pointer"
                {...props}
              >
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
            return (
              <th className="border border-neutral-700 bg-neutral-800 px-2 py-1 text-left">
                {children}
              </th>
            );
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