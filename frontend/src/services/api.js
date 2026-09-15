import axios from 'axios';

const API_BASE = '/api';

export const createResearchRun = async (companyName, mode = 'full', websiteUrl = null, researchQuestion = null) => {
  const response = await axios.post(`${API_BASE}/research`, {
    company_name: companyName,
    mode: mode,
    website_url: websiteUrl,
    research_question: researchQuestion
  });
  return response.data;
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

