import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "file:///C:/Users/LENOVO/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const workspaceDir = "C:/Users/LENOVO/Documents/antigravity/modest-babbage";
const templatePath = "C:/Users/LENOVO/Downloads/HYPNEXIS26_Official_PPT_Template.pptx";
const draftPath = path.join(workspaceDir, ".presentation-build/draft/HYPNEXIS26_DataTrust_AI_draft.pptx");
const renderDir = path.join(workspaceDir, ".presentation-build/draft/rendered");

const presentation = await PresentationFile.importPptx(await FileBlob.load(templatePath));

function setText(id, text, style) {
  const shape = presentation.resolve(id);
  shape.text = text;
  if (style) shape.text.style = style;
}

// Cover details. The official team and problem statement identifiers were not supplied.
setText("sh/utg3698n", "DataTrust AI");
setText("sh/hofulsf2", "Not provided");
setText("sh/vmdcj2xw", "Not provided");
setText("sh/5sfepcfe", "Trustworthy Knowledge Base");
setText("sh/3qxwn2x8", "AI & Data Engineering");
setText("sh/dgzetcfa", "Software");

// Slide 2: problem, solution, and a measured local benchmark.
setText("sh/9072xkry", "DATATRUST AI");
setText("sh/ozy1ofad", "DataTrust AI  |  Team ID pending");
setText("sh/x4r21kru", "Files change but indexes can go stale.\nConflicting sources need both claims shown.\nPrompt injections and language gaps erode trust.");
setText("sh/q5wjelsz", "Incremental add, edit and delete.\nKeep both claims with their source records.\nAnswer Hindi questions over English documents.");
setText(
  "sh/9wnqhczy",
  "500 documents in 7.7 seconds\n504 docs · 539 entities · 40 edges\nIsolated local benchmark",
  { fontSize: 20, typeface: "Arial", color: "#FFFFFF", bold: true, italic: false, alignment: "center" },
);

// Slide 3: implementation and the retrieval path.
setText("sh/d0jax03i", "DataTrust AI  |  Team ID pending");
setText("sh/obq90bml", "Documents enter through FastAPI and pass a safety filter. SQLite indexes terms, claims and graph links. Hindi/English retrieval finds evidence paths and returns source-backed answers.");
setText("sh/n6ls3alk", "Python + FastAPI backend\nSQLite document and graph stores\nReact + TypeScript + Vite frontend");
setText("sh/943mhgre", "Each document updates without a full rebuild.\nConflicts remain visible with source paths.");

// Slide 4: user-facing flow.
setText("sh/0ba143al", "DataTrust AI  |  Team ID pending");
setText("sh/doj29oba", "Ask in Hindi or English. Edit documents in Data Studio. Review source conflicts and graph paths.");
setText("sh/5cva1cfq", "Ask a question\nor ingest documents");
setText("sh/w72947yt", "Retrieve claims\nand graph links");
setText("sh/v6tsv2xo", "Review sourced\nanswer or conflict");
setText("sh/p0batw72", "Trace each answer to its source documents and graph paths.");
setText("sh/oz29krqh", "Question → claim → source document");

// Slide 5: feasibility, costs and operational limits.
setText("sh/cf2tcr61", "DataTrust AI  |  Team ID pending");
setText("sh/l4bupwny", "Python/FastAPI and SQLite run locally.\nBatch API accepts up to 2,000 docs/request.\nNo external model is needed for the test flow.");
setText("sh/m5kbi1oj", "Prototype uses the installed local stack.\nTest flow requires no paid API key.\nHosting and integration costs are unmeasured.");
setText("sh/ahkvi1cb", "Local app runs on ports 5173 and 8001.\nExtraction rules need broader corpus checks.\nConflicts remain visible for human review.");

// Slide 6: separate measured technical results from unmeasured impact.
setText("sh/zi98nu94", "DataTrust AI  |  Team ID pending");
setText("sh/oryp8fah", "Hindi users can query English documents.\nConflicts show both claims and sources.");
setText("sh/u1kbu1ov", "Updates reindex one document, not the full corpus.\nEnergy and carbon savings are not measured.");
setText("sh/twfux0ne", "500 input docs ingested in 7.7 s (local test).\nGraph: 504 docs, 539 entities, 40 edges.\n21 planted instruction strings tested.");
setText("sh/bq547yhw", "Inspect claims, sources and graph paths.\nEvidence replay makes grounded answers teachable.");

// Slide 7: clearly label the business model as a proposal.
setText("sh/dcbud0ra", "DataTrust AI  |  Team ID pending");
setText("sh/kzmdova1", "Compliance and operations analysts\nData teams combining SQL and documents\nHindi users working with English records");
setText("sh/fi9c369c", "Current stage: working prototype\nProposed: private institutional deployment\nCosts: hosting, integrations and support");
setText("sh/xcz2l03q", "Proposed: pilot with one team\nAdd source connectors as needed\nMeasure cost and update speed before scaling");

// Slide 8: project source files used to substantiate the presentation.
setText("sh/g72x4zyd", "DataTrust AI  |  Team ID pending");
setText(
  "sh/tkby9kzm",
  "README.md — architecture, setup and Phase 2 API\ndocument_store.py + graph_engine.py — index and graph updates\nvalidation_engine.py — evidence paths and conflict answers\ntest_phase2_documents.py — 500 docs, conflicts, injection and Hindi checks",
);

// Slide 9: preserve the template's close and identify missing contact details.
setText("sh/nex4jq5k", "DataTrust AI  |  Team ID: not provided  |  Contact: not provided");

const notesBySlide = [
  "The title is a concise description of the user-supplied Phase 2 extension. Team ID, official problem statement ID, and contact details were not included in the source materials.",
  "Sources: README.md (Phase 2 section); backend/app/document_store.py; backend/app/graph_engine.py; backend/tests/test_phase2_documents.py. The 7.7-second result is from an isolated local test database with 500 generated input documents. The graph total includes four seeded sample documents.",
  "Sources: README.md (Architecture Overview and Phase 2); backend/app/document_safety.py; backend/app/document_store.py; backend/app/graph_engine.py; backend/app/retrieval_engine.py; backend/app/validation_engine.py.",
  "Sources: frontend/src/App.tsx and frontend/src/components/DataStudioView.tsx. The user flow summarizes the current local application behavior.",
  "Sources: README.md (Quick Start and Phase 2); backend/app/main.py; backend/app/models.py. This deck describes the local prototype; operational constraints are identified as implementation limits.",
  "Measured result: 500 generated documents ingested in 7,675.74 ms in an isolated local test run; resulting graph size was 504 documents, 539 entities, and 40 relationships. The 504 document total includes four sample documents. Injection filtering was exercised with 21 planted instruction strings. No energy or carbon measurements were made. Source: backend/tests/test_phase2_documents.py and local benchmark response.",
  "The deployment and revenue model on this slide is a proposal for future pilots, not current revenue or a confirmed commercial plan.",
  "All references are project source files; no external research claims were added. The benchmark is synthetic and should not be presented as a production-corpus result.",
  "Team ID and contact information were not supplied and are marked accordingly.",
];

for (const [index, slide] of presentation.slides.items.entries()) {
  const existing = slide.speakerNotes.text?.trim() ?? "";
  slide.speakerNotes.text = [existing, notesBySlide[index]].filter(Boolean).join("\n\n");
}

await fs.mkdir(renderDir, { recursive: true });
for (const [index, slide] of presentation.slides.items.entries()) {
  const stem = `slide-${String(index + 1).padStart(2, "0")}`;
  const png = await presentation.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(path.join(renderDir, `${stem}.png`), new Uint8Array(await png.arrayBuffer()));
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(path.join(renderDir, `${stem}.layout.json`), await layout.text());
}

const deck = await PresentationFile.exportPptx(presentation);
await deck.save(draftPath);
console.log(JSON.stringify({ slideCount: presentation.slides.items.length, draftPath, renderDir }));
