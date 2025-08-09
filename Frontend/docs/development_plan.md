Frontend Development Plan (TypeScript/React, Docker, Kubernetes)

Phase 1: Foundation & Setup

    Project Initialization:
        Set up React project using Vite or Create React App with the TypeScript template.
        Install core dependencies: react-router-dom.
        Choose and set up a styling solution (e.g., CSS Modules, Tailwind CSS, Material UI, Chakra UI).
        Set up basic project structure (components, pages/views, services/api, contexts/store).
    Initial Dockerization:
        Create a Dockerfile for the React application (multi-stage build recommended: build static assets then serve with Nginx or similar).
        Update docker-compose.yml to include the frontend service.
        Goal: Ensure the basic React app builds and serves via Docker Compose. Configure proxying for API requests in development (vite.config.ts or CRA proxy setup).
    Core Layout & Routing:
        Implement main application layout (header, footer, navigation).
        Set up basic page routing using react-router-dom (e.g., Home, Login, Register, Dashboard).

Phase 2: Authentication & Basic Views

    API Client Setup:
        Set up a service/utility for making API calls to the backend (e.g., using axios or Workspace). Include handling for base URL, setting auth tokens (JWT).
    Authentication UI:
        Create Login and Registration pages/forms.
        Implement logic to call backend auth endpoints.
        Implement logic to store/clear JWT upon login/logout (e.g., localStorage, Context API, state management library).
        Implement protected routes that require authentication.
    Initial Dashboard/Home: Create a basic landing page for logged-in users.

Phase 3: Core Feature Implementation (Consuming Backend APIs)

    Car Management UI:
        Create components/pages to list the user's cars (fetch from /api/.../cars).
        Create forms to add/edit cars (POST/PUT to /api/.../cars).
        Implement delete functionality.
    Part Management UI:
        Create components/pages to list/search user's parts (GET from /api/.../parts).
        Create forms to add/edit parts (POST/PUT to /api/.../parts).
        Implement delete functionality.
        Note: UI complexity depends heavily on whether parts are user-specific or global (global needs search/filtering).
    State Management (If needed): As complexity grows, consider a dedicated state management library (Zustand, Redux Toolkit, Jotai) or rely heavily on React Context API + hooks.

Phase 4: Build List UI & Sharing

    Build List Management UI:
        Create components/pages to list user's build lists (GET from /api/.../buildlists).
        Create forms/flow to create new build lists (associating with one of the user's cars).
        Implement UI to view a specific build list.
        Implement UI to add/remove parts from a list (requires searching/selecting available parts and calling relevant backend endpoints).
    Sharing View:
        Create a dedicated page/route (e.g., /share/list/:listId) that fetches data using the public sharing endpoint (GET /api/v1/share/lists/{list_id}) and displays the list details read-only.

Phase 5: Refinement & Docker

    UI Polish: Improve styling, responsiveness, user experience.
    Error Handling & Loading States: Implement robust handling for API errors and display loading indicators during API calls.
    Final Docker Build: Ensure the production build works correctly within the Docker container, serving static assets efficiently.

Phase 6: Kubernetes Deployment (Learning Goal)

    Kubernetes Manifests:
        Write Kubernetes YAML manifests for the frontend:
            Deployment: To manage frontend server pods (e.g., Nginx serving static files).
            Service: To expose the frontend pods internally.
            Possibly ConfigMap if frontend needs runtime configuration passed from K8s.
    Local K8s Deployment: Deploy frontend manifests alongside backend manifests in your local cluster.
    Ingress Configuration: Update/configure the Ingress resource to route traffic:
        Requests to /api/* (or similar) should go to the backend Service.
        All other requests (/) should go to the frontend Service.
    (Stretch) Cloud K8s Deployment: Deploy frontend manifests to your managed Kubernetes service.
