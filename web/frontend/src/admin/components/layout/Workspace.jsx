// src/admin/components/layout/Workspace.jsx — Section 7 exact contract
import { lazy, Suspense } from "react";
import { useUI } from "../../../state/UIContext";
import Loader from "../shared/Loader";

import MetadataEditor   from "../editors/MetadataEditor";
import NounClassEditor  from "../editors/NounClassEditor";
import ConcordEditor    from "../editors/ConcordEditor";
import VerbSystemEditor from "../editors/VerbSystemEditor";
import VerifyManager    from "../editors/VerifyManager";
import DebugView        from "../../views/DebugView";
import EditorView       from "../../views/EditorView";
import VerifyView       from "../../views/VerifyView";

// Lazy-load quiz and learning modules — they are larger and less frequently used
const QuizPanel     = lazy(() => import("../../../quiz/QuizPanel"));
const LearningPanel = lazy(() => import("../../../learning/LearningPanel"));

// Tab id → component — add new views here only; no other file changes required
const VIEWS = {
  meta:     <MetadataEditor   />,
  nc:       <NounClassEditor  />,
  concords: <ConcordEditor    />,
  verb:     <VerbSystemEditor />,
  verify:   <VerifyManager    />,
  debug:    <DebugView        />,
  editor:   <EditorView       />,
  vview:    <VerifyView       />,
  analyze:  <DebugView        />,   // student alias for the parser view
  quiz:     <QuizPanel        />,
  learn:    <LearningPanel    />,
};

export default function Workspace() {
  const { activeView } = useUI();

  return (
    <main className="flex-1 overflow-y-auto p-6 bg-ggt-bg">
      <Suspense fallback={<Loader text="Loading view…" />}>
        {VIEWS[activeView] ?? (
          <div className="text-ggt-muted font-sans text-xs p-10 text-center">
            View "{activeView}" is not yet implemented.
          </div>
        )}
      </Suspense>
    </main>
  );
}
