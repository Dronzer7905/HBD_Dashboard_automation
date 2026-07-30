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

// Fix #5: Global 401 response interceptor — clears stale JWT and redirects
// to login so expired-token failures never silently break pages again.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      // Avoid redirect loops if already on the sign-in page
      if (!window.location.pathname.includes("/auth/sign-in")) {
        window.location.href = "/auth/sign-in";
      }
    }
    return Promise.reject(error);
  }
);

export default api;