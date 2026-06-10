import { FC } from "react";

export type PaperworkPanelProps = {
  dealSession: any;
  onAction: (action: string, payload?: any) => void;
  pdfUrl?: string;
  validationErrors?: string[];
};

const ACTIONS = [
  { key: "add-trade", label: "Add Trade" },
  { key: "update-price", label: "Update Price" },
  { key: "generate-paperwork", label: "Generate Paperwork" },
  { key: "print-all", label: "Print All" },
];

const PaperworkPanel: FC<PaperworkPanelProps> = ({ dealSession, onAction, pdfUrl, validationErrors }) => {
  return (
    <aside className="h-full flex flex-col bg-imperial-surface dark:bg-imperial-surface-dark border-l border-imperial-border dark:border-imperial-border-dark p-4 min-w-[320px] max-w-full">
      <h2 className="text-xl font-semibold mb-2 text-imperial-primary dark:text-imperial-primary-light">Paperwork</h2>
      {/* Live deal session summary */}
      <div className="mb-4">
        <h3 className="font-semibold text-base mb-1 text-imperial-text dark:text-imperial-text-dark">Deal Summary</h3>
        {dealSession ? (
          <pre className="bg-imperial-bg-light dark:bg-imperial-bg-dark rounded p-2 text-xs overflow-x-auto border border-imperial-border dark:border-imperial-border-dark text-imperial-text dark:text-imperial-text-dark">
            {JSON.stringify(dealSession, null, 2)}
          </pre>
        ) : (
          <p className="text-imperial-text-secondary dark:text-imperial-text-secondary-dark text-sm">No active deal session.</p>
        )}
      </div>
      {/* Validation errors */}
      {validationErrors && validationErrors.length > 0 && (
        <div className="mb-4">
          <h4 className="text-imperial-danger font-semibold text-sm mb-1">Validation Errors</h4>
          <ul className="list-disc pl-5 text-imperial-danger text-xs">
            {validationErrors.map((err, idx) => (
              <li key={idx}>{err}</li>
            ))}
          </ul>
        </div>
      )}
      {/* Action buttons */}
      <div className="flex flex-wrap gap-2 mb-4">
        {ACTIONS.map((action) => (
          <button
            key={action.key}
            className="px-3 py-2 rounded font-semibold text-xs min-h-[44px] min-w-[44px] focus:outline-none focus:ring-2 focus:ring-imperial-primary focus:ring-offset-2 transition-colors duration-150 bg-imperial-gold text-imperial-primary hover:bg-imperial-primary-light hover:text-white"
            onClick={() => onAction(action.key)}
            aria-label={action.label}
          >
            {action.label}
          </button>
        ))}
      </div>
      {/* PDF Preview/Download */}
      {pdfUrl && (
        <div className="mt-2">
          <a
            href={pdfUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block text-imperial-primary underline text-xs font-semibold hover:text-imperial-gold focus:outline-none focus:ring-2 focus:ring-imperial-primary focus:ring-offset-2"
            aria-label="Download or preview PDF"
          >
            Download/Preview PDF
          </a>
        </div>
      )}
    </aside>
  );
};

export default PaperworkPanel;
