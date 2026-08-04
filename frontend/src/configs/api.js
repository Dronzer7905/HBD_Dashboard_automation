import axios from 'axios';

// 1. Force the API Base URL to point to your Python server port
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8001/api";

// 2. Create the Axios Instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// 3. Request Interceptor: Automatically extract and inject the JWT token
api.interceptors.request.use(
  (config) => {
    let token = null;

    // Scan localStorage keys to find the one containing the actual JWT signature
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      const value = localStorage.getItem(key);
      
      // A real JWT token contains "eyJhbGci"
      if (value && value.includes("eyJhbGci")) {
        // Robust match pattern to isolate the JWT token (ignoring surrounding quotes/text)
        const match = value.match(/eyJhbGci[a-zA-Z0-9_\-\.]+/);
        if (match) {
          token = match[0];
          break;
        }
      }
    }

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    } else {
      console.error("DEBUG: Request Interceptor failed to resolve a valid JWT token (starting with 'eyJhbGci') from localStorage.");
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 4. Response Interceptor for Logging and Auth redirection
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error("API Connection Error:", error);
    if (error.response && error.response.status === 401) {
      // Clear token from localStorage
      localStorage.removeItem("token");
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        const value = localStorage.getItem(key);
        if (value && value.includes("eyJhbGci")) {
          localStorage.removeItem(key);
        }
      }
      console.warn("API 401 Unauthorized: Redirecting to login...");
      window.location.href = "/auth/sign-in";
    }
    return Promise.reject(error);
  }
);

export default api;