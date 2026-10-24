import path from "node:path";
import { pathToFileURL } from "node:url";

const workspaceDir = "C:/Users/LENOVO/Documents/antigravity/modest-babbage";
const skillDir = "C:/Users/LENOVO/.codex/plugins/cache/openai-primary-runtime/presentations/26.1022.11436/skills/presentations";
const templatePath = "C:/Users/LENOVO/Downloads/HYPNEXIS26_Official_PPT_Template.pptx";
const runtimePython = "C:/Users/LENOVO/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";
const candidatePath = path.join(workspaceDir, ".presentation-build/draft/HYPNEXIS26_DataTrust_AI_draft.pptx");
const finalPath = path.join(workspaceDir, "deliverables/HYPNEXIS26_DataTrust_AI.pptx");
const { finalizePresentation } = await import(pathToFileURL(path.join(skillDir, "container_tools/artifact_tool_utils.mjs")).href);

const result = await finalizePresentation({
  explicitTotalSlideCount: 9,
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: runtimePython,
  integrityValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", "12192000,6858000",
    "--validate-bullet-geometry",
    "--validate-heading-fit",
  ],
  fontPolicy: {
    basis: "reference",
    families: ["Arial", "Calibri"],
    referencePath: templatePath,
    referenceSha256: "21b04928a7d0edf432536c702de753a905862954f9ad7580d1e9a4dc11a49404",
  },
  verifyArtifactToolImport: true,
  receiptPath: path.join(workspaceDir, ".presentation-build/draft/HYPNEXIS26_DataTrust_AI.validation.json"),
});

console.log(JSON.stringify(result, null, 2));
