import axios from 'axios';

const API_BASE = '/api';

export const createResearchRun = async (
  companyName,
  mode = 'full',
  websiteUrl = null,
  researchQuestion = null
) => {
  const response = await axios.post(`${API_BASE}/research`, {
    company_name: companyName,
    mode,
    website_url: websiteUrl,
    research_question: researchQuestion,
  });
  return response.data;
};

/**
 * Kicks off the pipeline. This request stays open for the whole run
 * (up to ~5 min), so we deliberately do NOT await it — the Status page
 * polls getResearchStatus() for progress instead.
 */
export const executeResearchRun = (runId) => {
  axios
    .post(`${API_BASE}/research/${runId}/execute`, null, { timeout: 0 })
    .catch((err) => {
      // A dropped/aborted connection here is expected and harmless; the
      // run's real outcome is whatever the status endpoint reports.
      console.debug('execute request ended', err?.message);
    });
};

export const getResearchStatus = async (runId) => {
  const response = await axios.get(`${API_BASE}/research/${runId}`);
  return response.data;
};

export const getResearchReport = async (runId) => {
  const response = await axios.get(`${API_BASE}/research/${runId}/report`);
  return response.data;
};

export const getResearchSources = async (runId) => {
  const response = await axios.get(`${API_BASE}/research/${runId}/sources`);
  return response.data;
};