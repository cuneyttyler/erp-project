import axios from 'axios'

// Shared typed API client (technical.md §10.3). Every package module's store
// calls through this instance rather than instantiating its own axios client,
// so auth headers / base URL / error handling stay in one place. Once the DRF
// OpenAPI schema (technical.md §6) is generated, per-resource typed wrappers
// are generated from it rather than hand-maintained here.
export const apiClient = axios.create({
  baseURL: '/api/v1/',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
  // DRF's SessionAuthentication enforces Django's normal CSRF check on
  // unsafe methods -- axios reads the csrftoken cookie (set by GET
  // /core/auth/csrf/, see shared/stores/auth.ts) and echoes it back as this
  // header automatically on every request once the cookie exists.
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Centralized error normalization lands here once the backend's error
    // response shape is defined — placeholder for now.
    return Promise.reject(error)
  },
)
