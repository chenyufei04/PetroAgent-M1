const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `请求失败：${response.status}`);
  }
  return response.json();
}

export const getCases = () => request("/api/cases");
export const uploadDataset = async (file, caseId, sheetName = "") => {
  const form = new FormData();
  form.append("file", file);
  form.append("case_id", caseId);
  if (sheetName) form.append("sheet_name", sheetName);
  const response = await fetch(`${API_BASE}/api/datasets/upload`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `上传失败：${response.status}`);
  }
  return response.json();
};
export const runAnalysis = (caseId, datasetId = null) =>
  request("/api/analysis/run", {
    method: "POST",
    body: JSON.stringify({ case_id: caseId, dataset_id: datasetId }),
  });
export const getSubgraph = (conceptIds) =>
  request("/api/graph/subgraph", {
    method: "POST",
    body: JSON.stringify({ concept_ids: conceptIds, limit: 100 }),
  });
export const getGraphView = (view = "all", limit = 200) =>
  request("/api/graph/view", {
    method: "POST",
    body: JSON.stringify({ view, limit }),
  });
export const outputUrl = (path) => `${API_BASE}${path}`;
export const getOutputPreview = (path) => request(path);
