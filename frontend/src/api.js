// 默认使用同源相对地址：本地由 Vite 代理，生产环境由 FastAPI/Cloudflare 同域转发。
// 仅在前后端确实部署到不同域名时，才通过 VITE_API_BASE 显式指定后端地址。
const API_BASE = (import.meta.env.VITE_API_BASE || "").replace(/\/$/, "");

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
export const getClientInfo = () => request("/api/client-info");
export const getExperiments = () => request("/api/experiments");
export const getExperiment = (experimentId) => request(`/api/experiments/${experimentId}`);
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
export const getExperimentRankings = (experimentId) =>
  request(`/api/graph/experiments/${experimentId}/rankings`);
export const getScenarioExplanation = (experimentId, caseId) =>
  // 多领域适配说明：解释链接口是通用契约，新领域应保持该路径和响应结构不变。
  request(`/api/experiments/${experimentId}/cases/${caseId}/explanation`);
export const getScenarioContext = (experimentId, caseId) =>
  request(`/api/experiments/${experimentId}/cases/${caseId}/context`);
export const getAssistantStatus = () => request("/api/assistant/status");
export const chatWithAssistant = (experimentId, caseId, question, history = []) =>
  request("/api/assistant/chat", {
    method: "POST",
    body: JSON.stringify({ experiment_id: experimentId, case_id: caseId, question, history }),
  });
export const outputUrl = (path) => `${API_BASE}${path}`;
export const getOutputPreview = (path) => request(path);
