import webview
import threading
import os
import re
from plugin_manager import PluginManager
from dotenv import load_dotenv
load_dotenv()
from context_manager import ContextManager
from js_api import Api
from settings_manager import SettingsManager
from prompts import AssistantPrompts
from websocket_server import websocket_server
import signal,sys
import tkinter as tk

prompts=None
context_manager = ContextManager()


def show_splash_screen(image_path):
    """Create a simple splash screen with a logo."""
    splash_root = tk.Tk()
    splash_root.overrideredirect(True)  # Remove window borders
    splash_root.geometry('500x200+500+300')  # Set splash size and position

    # Load your logo/image
    splash_image = tk.PhotoImage(file=image_path)
    splash_label = tk.Label(splash_root, image=splash_image)
    splash_label.pack()

    # Display splash screen
    splash_root.update()  # Refresh the window
    return splash_root


def signal_handler(sig, frame):
    print('Exiting application...')
    os._exit(0)
    
signal.signal(signal.SIGINT, signal_handler)

# VARS HERE
IGOOR_DEBUG = os.getenv('IGOOR_DEBUG', 'False') 
IGOOR_CLI = os.getenv('IGOOR_CLI', 'False') 
IGOOR_OUTPUT_HTML = os.getenv('IGOOR_OUTPUT_HTML', 'False') 

def load_settings():
    settings = SettingsManager();
    # print("Current settings:", settings)
    return settings

def load_frontend_components():
    manager = PluginManager()
    # active_plugins = ["flow","asrvosk","rag"]
    # exclude_plugins = ["ramcpu","clock","elevenlabs","meteo"]
    active_plugins=[]
    exclude_plugins=[]
    manager.load_plugins(active_list=active_plugins,exclude_list=exclude_plugins)
    plugins_metadata = manager.get_plugins_metadata()
    # print("Plugins metadata:", plugins_metadata)  # Debugging output

    # Components organized by category
    components_by_category = {
        'hidden': [],
        'topbar': [],
        'header': [],
        'after_header': [],
        'main': [],
        'footer': []
    }

    # Iterate over plugins metadata
    for plugin_name, metadata in plugins_metadata.items():
        if metadata.get('active', False):  # Check if plugin is active
            print ("Plugin " + plugin_name + " is active")
            component_name = ''.join(word.capitalize() for word in plugin_name.split('_'))
            component_path = f"/plugins/{plugin_name}/frontend/{plugin_name}_component.vue"
            
            component_definition = {
                'name': component_name,
                'path': component_path,
                'order': metadata.get('layout', {}).get('order', 0)
            }
            
            category = metadata.get('layout', {}).get('part', 'main')
            if category in components_by_category:
                components_by_category[category].append(component_definition)
        else:
            print(f"The plugin '{plugin_name}' is not activated.")

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

    # Load and modify the template HTML
    with open('js/app_template.vue', 'r') as f:
        html_content = f.read()
        
    # Define the placeholders and their corresponding replacements
    replacements = {
        '<!-- HIDDEN_COMPONENTS -->': ''.join(f'<{comp["name"].lower()}></{comp["name"].lower()}>' for comp in components_by_category['hidden']),
        '<!-- TOPBAR_COMPONENTS -->': ''.join(f'<{comp["name"].lower()}></{comp["name"].lower()}>' for comp in components_by_category['topbar']),
        '<!-- HEADER_COMPONENTS -->': ''.join(f'<{comp["name"].lower()}></{comp["name"].lower()}>' for comp in components_by_category['header']),
        '<!-- AFTER_HEADER_COMPONENTS -->': ''.join(f'<{comp["name"].lower()}></{comp["name"].lower()}>' for comp in components_by_category['after_header']),
        '<!-- MAIN_COMPONENTS -->': ''.join(f'<{comp["name"].lower()}></{comp["name"].lower()}>' for comp in components_by_category['main']),
        '<!-- FOOTER_COMPONENTS -->': ''.join(f'<{comp["name"].lower()}></{comp["name"].lower()}>' for comp in components_by_category['footer'])
    }

    # Replace all placeholders in the HTML content
    for placeholder, replacement in replacements.items():
        html_content = html_content.replace(placeholder, replacement)

    # Insert the Vue loader script into HTML content
    final_html = html_content

    # Write the final vue to app.vue
    with open('js/app.vue', 'w') as f:
        f.write(final_html)
        f.close()
    
    # Load and modify the JAVASCRIPT
    with open('js/app_template.js', 'r') as f:
        js_content = f.read()
    
    replacements = {
        '//** JS_COMPONENTS */': ', '.join(vue_component_definitions)
    }        
    
    # Replace all placeholders in the HTML content
    for placeholder, replacement in replacements.items():
        js_content = js_content.replace(placeholder, replacement)
    
    # Load and modify the JAVASCRIPT
    with open('js/app.js', 'w') as f:
        js_content = f.write(js_content)  

    return final_html

def get_full_context():
    """
    Retrieves the full context from the context manager.
    Returns:
        dict: The full context.
    """
    return context_manager.get_context()

def start_webview():
    try:
        webview.create_window("IGOOR", "index.html", js_api=Api(), resizable=True)  # fullscreen=True if needed
        webview.start(debug=IGOOR_DEBUG.lower() == 'true')
    except KeyboardInterrupt:
        print("KeyboardInterrupt detected. Shutting down...")
        
        # Safely close the websocket server
        websocket_server.stop()  # Make sure you have a stop method to close connections and resources
        
        print("WebSocket server has been closed.")    
        os._exit()


if __name__ == "__main__":
    splash_screen = show_splash_screen('img/igoor_logo.png')
    settings = load_settings();
    
    if IGOOR_CLI.lower() != 'true':
        final_html = load_frontend_components()
        if (IGOOR_OUTPUT_HTML.lower() == 'true'):
            print(final_html)
    
    s = settings.get_all_settings()    
    user=s.get("user")
    print (user)
    lang = user.get("lang")
    print ("lang = " + lang)
    prompts = AssistantPrompts("locales/",lang)
    # LAUNCH WINDOW APP
    if IGOOR_CLI.lower() != 'true':
        splash_screen.destroy()
        start_webview()
    else:
        print(get_full_context())
        
