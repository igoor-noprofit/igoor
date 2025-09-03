from version import __appname__, __version__, __codename__
import webview
import threading
import os
import re
from dotenv import load_dotenv
load_dotenv()
from plugin_manager import PluginManager
from context_manager import ContextManager
from js_api import Api
from settings_manager import SettingsManager
from websocket_server import websocket_server
import signal,sys
import tkinter as tk
import asyncio
from utils import resource_path, setup_logger
from idle_detector import IdleDetector


appdata_dir = os.path.join(os.getenv('APPDATA'), __appname__)
if not os.path.exists(appdata_dir):
    os.makedirs(appdata_dir)
logger = setup_logger('main', appdata_dir)
prompts=None
context_manager = ContextManager()
manager = PluginManager()

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
    on_closing()
    
signal.signal(signal.SIGINT, signal_handler)

# VARS HERE
IGOOR_DEBUG = os.getenv('IGOOR_DEBUG', 'False') 
IGOOR_CLI = os.getenv('IGOOR_CLI', 'False') 
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
    with open(resource_path('js/app_template.vue'), 'r') as f:
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

    # Write the final vue to app.vue
    with open(resource_path('js/app.vue'), 'w') as f:
        f.write(final_html)
        f.close()
    
    # Load and modify the JAVASCRIPT
    with open(resource_path('js/app_template.js'), 'r') as f:
        js_content = f.read()

    js_content = js_content.replace('{{LANG}}', f'{lang}')

    replacements = {
        '//** JS_COMPONENTS */': ', '.join(vue_component_definitions)
    }        
    
    # Replace all placeholders in the HTML content
    for placeholder, replacement in replacements.items():
        js_content = js_content.replace(placeholder, replacement)
    
    # Load and modify the JAVASCRIPT
    with open(resource_path('js/app.js'), 'w') as f:
        f.write(js_content)  

    return final_html

def on_closing():
    websocket_server.stop()  # Make sure you have a stop method to close connections and resources
    print("WebSocket server has been closed.")

def on_loaded():
    logger.info("GUI window is now loaded and available!")
    asyncio.run(manager.trigger_hook("gui_ready"))
    prefs = settings.get_prefs()
    idle_threshold = prefs.get("idle_threshold", 10)
    print(f"idle_threshold = {idle_threshold}")
    detector = IdleDetector(callback=on_idle_change, idle_threshold=idle_threshold, check_interval=10) 
    detector.start()
    return True

def start_webview():
    try:
        fullscreen = os.getenv('IGOOR_FULLSCREEN', 'False').lower() == 'true'
        on_top = os.getenv('IGOOR_ONTOP', 'False').lower() == 'true'
        window = webview.create_window("IGOOR", "index.html", js_api=Api(), 
                                        resizable=True, fullscreen=fullscreen,on_top=on_top)
        window.events.loaded += on_loaded
        window.events.closing += on_closing
        webview.start(debug=IGOOR_DEBUG.lower() == 'true')
    except KeyboardInterrupt:
        logger.warning("KeyboardInterrupt detected. Shutting down...")
        on_closing()

if __name__ == "__main__":
    splash_screen = show_splash_screen('img/igoor_logo.png')
    settings = load_settings()
    bio = settings.get_nested(["plugins", "onboarding", "bio"], default={})
    logger.info(bio)
    prefs = settings.get_nested(["plugins", "onboarding", "prefs"], default={})
    lang = prefs.get("lang")
    
    if IGOOR_CLI.lower() != 'true':
        final_html = load_frontend_components(lang=lang)
        if (IGOOR_OUTPUT_HTML.lower() == 'true'):
            print(final_html)
            
    # LAUNCH WINDOW APP
    if IGOOR_CLI.lower() != 'true':
        splash_screen.destroy()
        start_webview()
    else:
        print("CLI ONLY VERSION")

