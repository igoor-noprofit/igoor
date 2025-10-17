 Baseline Audit
     •  Map all pywebview/Bottle entry points (main.py, js_api.Api, plugin messaging
        helpers, load_frontend_components) and document request/response payloads to
        preserve behavior.

   2. FastAPI Core Setup
     •  Stand up an ASGI app with configuration (env, CORS, lifespan hooks).
     •  Mount primary static directory at APPDATA_FOLDER/web and serve only the writable
        app.js/app.vue from there; expose read-only css, img, plugins’ frontend assets,
        etc., directly from the install path via additional static mounts.

   3. WebSocket Infrastructure
     •  Replace the standalone WebSocketServer thread with FastAPI WebSocket routes
        (/ws/{plugin}), maintaining connection registries, handler registration, and
        broadcast helpers equivalent to the current API.

   4. Backend Refactor
     •  Inject the new WebSocket hub into Baseplugin (and plugin subclasses), updating        
        messaging utilities (wait_for_socket_and_send, send_message_to_frontend, etc.) for    
         async operation under FastAPI.
     •  Convert js_api.Api methods into REST endpoints (or WebSocket RPC handlers) and        
        adapt main.py startup to launch uvicorn (optionally inside pywebview).

   5. Frontend Adjustments
     •  Update BasePluginComponent.js (and related scripts) to use the FastAPI WebSocket      
        endpoints and replace window.pywebview.api calls with REST/websocket clients while    
         keeping translation/settings fetch paths intact.

   6. Ancillary Systems
     •  Ensure plugin settings, translations, and database helpers resolve through FastAPI    
         dependencies/state.
     •  Align background services (idle detector, status manager) with FastAPI
        lifespan/background task patterns.

   7. Testing & Validation
     •  Create ASGI integration tests (REST + WebSockets) covering plugin activation,
        settings updates, and messaging flows.
     •  Perform regression/performance checks (WebSocket fan-out, security validation)        
        before deployment.