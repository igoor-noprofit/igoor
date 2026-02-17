from version import __appname__, __version__, __codename__
import webview
import os
import time
from dotenv import load_dotenv
load_dotenv()
from plugin_manager import PluginManager
from context_manager import ContextManager
from js_api import Api
from settings_manager import SettingsManager
from websocket_server import websocket_server
import signal
import sys
import tkinter as tk
import asyncio
import threading
from typing import Optional
from utils import (
    resource_path,
    setup_logger,
    get_appdata_dir,
    get_appdata_web_js_dir,
    generate_self_signed_cert,
)
from fastapi_app import app as fastapi_app
import uvicorn
from idle_detector import IdleDetector

appdata_dir = get_appdata_dir(create=True)
logger = setup_logger('main', appdata_dir)
context_manager = ContextManager()
manager = PluginManager()
fastapi_server: Optional[uvicorn.Server] = None
fastapi_thread: Optional[threading.Thread] = None
shutdown_event = threading.Event()


def _write_dynamic_frontend_asset(file_name: str, content: str) -> str:
    js_web_dir = get_appdata_web_js_dir(create=True)
    appdata_path = os.path.join(js_web_dir, file_name)

    with open(appdata_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return appdata_path


def start_fastapi_server() -> None:
    global fastapi_server, fastapi_thread
    if fastapi_server and fastapi_thread and fastapi_thread.is_alive():
        return

    # Determine host based on LAN access setting
    access_from_outside = os.getenv('IGOOR_ACCESS_FROM_OUTSIDE', 'False').lower() == 'true'
    host = "0.0.0.0" if access_from_outside else "127.0.0.1"
    
    # SSL configuration for HTTPS (required for microphone access from LAN)
    ssl_keyfile = None
    ssl_certfile = None
    if access_from_outside:
        try:
            ssl_certfile, ssl_keyfile = generate_self_signed_cert()
            logger.info(f"SSL certificate generated: {ssl_certfile}")
        except Exception as e:
            logger.warning(f"Failed to generate SSL certificate: {e}")
            logger.warning("Microphone access from LAN will not work (requires HTTPS)")

    config = uvicorn.Config(
        fastapi_app,
        host=host,
        port=9714,
        log_level="info",
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile,
    )
    fastapi_server = uvicorn.Server(config)

    fastapi_thread = threading.Thread(target=fastapi_server.run, daemon=True)
    fastapi_thread.start()

    # Wait briefly for the server to signal readiness
    if hasattr(fastapi_server, "started"):
        while fastapi_thread.is_alive() and fastapi_server.started is False:
            time.sleep(0.05)


def stop_fastapi_server() -> None:
    global fastapi_server, fastapi_thread
    if fastapi_server:
        fastapi_server.should_exit = True

    if fastapi_thread and fastapi_thread.is_alive():
        fastapi_thread.join(timeout=5)

    fastapi_server = None
    fastapi_thread = None

def on_idle_change(is_idle):
    if is_idle:
        logger.info("User is now idle!")
        asyncio.run(manager.trigger_hook("user_idle_on_pc"))
    else:
        logger.info("User is now active!")
        # 10 MINUTES TOTAL INACTIVITY

def show_splash_screen(image_path):
    """Create a simple splash screen with a logo."""
    splash_root = tk.Tk()
    splash_root.overrideredirect(True)  # Remove window borders
    
    # Get screen dimensions
    screen_width = splash_root.winfo_screenwidth()
    screen_height = splash_root.winfo_screenheight()
    
    # Set window dimensions
    window_width = 500
    window_height = 200
    
    # Calculate center position
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    
    splash_root.geometry(f'{window_width}x{window_height}+{x}+{y}')
    
    # Configure grid weight to enable centering
    splash_root.grid_rowconfigure(0, weight=1)
    splash_root.grid_columnconfigure(0, weight=1)
    
    # Load your logo/image
    splash_image = tk.PhotoImage(file=resource_path(image_path))
    splash_label = tk.Label(splash_root, image=splash_image, bg='white')
    splash_label.grid(row=0, column=0, sticky='nsew')  # Use grid with sticky to center

    # Add version and codename below the logo
    version_text = f"IGOOR {IGOOR_VERSION} — {IGOOR_VERSION_CODENAME}"
    version_label = tk.Label(splash_root, text=version_text, bg='white', fg='#444', font=("Arial", 14, "bold"))
    version_label.grid(row=1, column=0, pady=(10, 0))

    # Configure window background
    splash_root.configure(bg='white')
    
    # Display splash screen
    splash_root.update()
    return splash_root


def signal_handler(sig, frame):
    logger.info('Exiting application...')
    shutdown_event.set()
    on_closing()
    
signal.signal(signal.SIGINT, signal_handler)

# VARS HERE
IGOOR_DEBUG = os.getenv('IGOOR_DEBUG', 'False')
IGOOR_HEADLESS = os.getenv('IGOOR_HEADLESS', 'False')
IGOOR_ONTOP = os.getenv('IGOOR_ONTOP', 'False') 
IGOOR_OUTPUT_HTML = os.getenv('IGOOR_OUTPUT_HTML', 'False') 
IGOOR_VERSION_CODENAME = __codename__
IGOOR_VERSION=__version__

def load_settings():
    settings = SettingsManager()
    return settings

def load_frontend_components(lang):
    '''
    Sort of webpack that constructs the final HTML frontend,
    based on the Vue components from the active plugins 
    '''
    active_plugins=[]
    exclude_plugins=[]
    manager.load_plugins(active_list=active_plugins,exclude_list=exclude_plugins)
    plugins_metadata = manager.get_plugins_metadata()
    
    # Get activation states from settings.json
    settings = SettingsManager()
    plugins_activation = settings.get_settings().get("plugins_activation", {})

    # Components organized by category
    components_by_category = {
        'hidden': [],
        'before_logo': [],  # New category
        'after_logo': [],   # New category
        'after_topbar': [],
        'header': [],
        'after_header': [],
        'main': [],
        'footer': []
    }

    # Iterate over plugins metadata
    for plugin_name, metadata in plugins_metadata.items():
        # Check activation state from settings.json instead of metadata
        if plugins_activation.get(plugin_name, False):
            logger.info(f"Plugin {plugin_name} is active")
            component_name = ''.join(word.capitalize() for word in plugin_name.split('_'))
            component_path = f"/plugins/{plugin_name}/frontend/{plugin_name}_component.vue"
            frontend = metadata.get('frontend', {})
            events = frontend.get('events', [])
            event_bindings = ' '.join(
                f'@{event_name}="{event_function}"' for event in events for event_name, event_function in event.items()
            )
            component_definition = {
                'name': component_name,
                'path': component_path,
                'order': metadata.get('layout', {}).get('order', 0),
                'event_bindings': event_bindings
            }
            
            category = metadata.get('layout', {}).get('part', 'main')
            if category in components_by_category:
                components_by_category[category].append(component_definition)
        # else:
            # print(f"The plugin '{plugin_name}' is not activated.")

    # Sort components by 'order'
    for category, components in components_by_category.items():
        components_by_category[category] = sorted(components, key=lambda x: x['order'])

    # print(components_by_category)
    # Prepare Vue components registration
    vue_component_definitions = []
    for category, components in components_by_category.items():
        for component in components:
            vue_component_definitions.append(
                f"'{component['name']}': Vue.defineAsyncComponent(() => loadModule('{component['path']}',options))"
            )

    # Load and modify the VUE template
    with open(resource_path('js/app_template.vue'), 'r', encoding="utf-8") as f:
        html_content = f.read()
        
    # Define the placeholders and their corresponding replacements
    # Also passes the appview variable
    replacements = {
        f'<!-- {category.upper()}_COMPONENTS -->': ''.join(
            f'<{comp["name"].lower()} {comp["event_bindings"]} :appview="appview" :lang="lang"></{comp["name"].lower()}>'
            for comp in components
        )
        for category, components in components_by_category.items()
    }

    # Replace all placeholders in the HTML content
    for placeholder, replacement in replacements.items():
        html_content = html_content.replace(placeholder, replacement)

    final_html = html_content

    app_vue_path = _write_dynamic_frontend_asset('app.vue', final_html)
    
    # Load and modify the JAVASCRIPT
    with open(resource_path('js/app_template.js'), 'r', encoding="utf-8") as f:
        js_content = f.read()

    js_content = js_content.replace('{{LANG}}', f'{lang}')

    replacements = {
        '//** JS_COMPONENTS */': ', '.join(vue_component_definitions)
    }        
    
    # Replace all placeholders in the HTML content
    for placeholder, replacement in replacements.items():
        js_content = js_content.replace(placeholder, replacement)
    
    app_js_path = _write_dynamic_frontend_asset('app.js', js_content)

    logger.info(f"Updated frontend files: {app_vue_path}, {app_js_path}")

    return final_html

def on_closing():
    stop_fastapi_server()
    websocket_server.stop()  
    print("WebSocket server has been closed.")

def on_loaded():
    global window
    logger.info("=== on_loaded function triggered ===")
    
    # Check if window object is available
    if window is None:
        logger.error("Window object is None! Cannot proceed with evaluate_js")
        return False
        
    # Attempt to bootstrap front-end readiness
    try:
        window.evaluate_js("window.app?.readypy?.();")
        logger.info("✓ readypy invocation dispatched")
    except Exception as e:
        logger.error(f"Failed to invoke readypy: {e}")
    
    try:
        asyncio.run(manager.trigger_hook("gui_ready"))
        logger.info("✓ gui_ready hook triggered successfully")
    except Exception as e:
        logger.error(f"Failed to trigger gui_ready hook: {e}")
    
    try:
        prefs = settings.get_prefs()
        idle_threshold = prefs.get("idle_threshold", 10)
        logger.info(f"idle_threshold = {idle_threshold}")
        
        detector = IdleDetector(callback=on_idle_change, idle_threshold=idle_threshold, check_interval=10) 
        detector.start()
        logger.info("✓ IdleDetector started successfully")
    except Exception as e:
        logger.error(f"Failed to start IdleDetector: {e}")
    
    return True

def start_webview():
    global window
    
    try:
        # Check if running as executable
        is_executable = getattr(sys, 'frozen', False)
        debug_enabled = (IGOOR_DEBUG.lower() == 'true')
        
        logger.info(f"Running as executable: {is_executable}")
        logger.info(f"Debug mode: {debug_enabled}")
        logger.info(f"Current working directory: {os.getcwd()}")
        
        # Check if index.html exists
        index_path = resource_path('index.html')
        logger.info(f"Looking for index.html at: {index_path}")
        if os.path.exists(index_path):
            logger.info("✓ index.html found")
        else:
            logger.error("✗ index.html NOT found")
            
        # Log webview configuration
        fullscreen = os.getenv('IGOOR_FULLSCREEN', 'False').lower() == 'true'
        on_top = os.getenv('IGOOR_ONTOP', 'False').lower() == 'true'
        
        logger.info(f"Webview config - fullscreen: {fullscreen}, on_top: {on_top}")
        
        # Create window
        logger.info("Creating webview window...")
        window = webview.create_window(
            "IGOOR", 
            "http://127.0.0.1:9714/index.html", 
            js_api=Api(), 
            resizable=True, 
            fullscreen=fullscreen,
            on_top=on_top,
            min_size=(1280,960)
        )
        
        if window is None:
            logger.error("Failed to create window - window is None")
            return
        else:
            logger.info("✓ Window created successfully")
            
        # Bind events
        logger.info("Binding window events...")
        window.events.loaded += on_loaded
        window.events.closing += on_closing
        logger.info("✓ Events bound successfully")
        
        # Start webview
        logger.info("Starting webview...")
        webview.settings['OPEN_DEVTOOLS_IN_DEBUG'] = False
        webview.start(debug=debug_enabled,private_mode=False)
        logger.info("✓ Webview started successfully")
        
    except Exception as e:
        logger.error(f"Critical error in start_webview: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    except KeyboardInterrupt:
        logger.warning("KeyboardInterrupt detected. Shutting down...")
        on_closing()

if __name__ == "__main__":
    settings = load_settings()
    bio = settings.get_nested(["plugins", "onboarding", "bio"], default={})
    prefs = settings.get_nested(["plugins", "onboarding", "prefs"], default={})
    lang = prefs.get("lang")

    # Log token if LAN access is enabled
    access_from_outside = os.getenv('IGOOR_ACCESS_FROM_OUTSIDE', 'False').lower() == 'true'
    if access_from_outside:
        token = settings.get_or_create_access_token()
        logger.info(f"LAN Access enabled. Token: {token}")
        logger.warning("Anyone with this token can access IGOOR on your network.")
        
        # Get local IP for logging
        import socket
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            logger.info(f"Access from LAN devices: https://{local_ip}:9714/")
        except Exception:
            pass
        
        logger.info("Your browser will show a security warning. Click 'Advanced' then 'Proceed anyway' to accept the certificate.")

    if IGOOR_HEADLESS.lower() == 'true':
        logger.info("IGOOR_HEADLESS active: running headless API/WebSocket server only")
        load_frontend_components(lang=lang)
        start_fastapi_server()
        try:
            while not shutdown_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutdown requested (headless mode)")
        finally:
            stop_fastapi_server()
    else:
        start_fastapi_server()
        splash_screen = show_splash_screen('img/igoor_logo.png')
        final_html = load_frontend_components(lang=lang)
        if (IGOOR_OUTPUT_HTML.lower() == 'true'):
            print(final_html)
        splash_screen.destroy()
        start_webview()

