import axios from "axios";

const api = axios.create({
  // Direct connection to Flask backend on port 8001
  baseURL: `${import.meta.env.VITE_API_URL || ""}/api`,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(
  (config) => {
    // Strip leading slash so browser doesn't treat it as an absolute root path overriding baseURL
    if (config.url && config.url.startsWith('/')) {
      config.url = config.url.substring(1);
    }
    
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default api;