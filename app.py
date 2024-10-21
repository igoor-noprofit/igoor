import webview
import os
import re
from plugin_manager import PluginManager
from dotenv import load_dotenv
load_dotenv()
# VARS HERE
IGOOR_DEBUG = os.getenv('IGOOR_DEBUG', 'False') 
IGOOR_CLI = os.getenv('IGOOR_CLI', 'False') 
IGOOR_OUTPUT_HTML = os.getenv('IGOOR_OUTPUT_HTML', 'False') 

def load_frontend_components():
    manager = PluginManager()
    
    # Load activated plugins
    activated_plugins = manager.get_activated_plugins()
    print("Activated plugins:", activated_plugins)  # Debugging output

    # Store component paths and names
    component_js_definitions = []
    component_names = []

    # Iterate through activated plugins
    for plugin_name, is_active in activated_plugins.items():
        if is_active:  # Check if the plugin is active
            # Define the path to the Vue component and fix the slashes
            component_key = f"{plugin_name}_component.vue"  # Assuming the component naming convention
            vue_path = os.path.join("plugins", plugin_name, "frontend", component_key)
            
            # Use forward slashes in the URL
            vue_path = vue_path.replace(os.sep, '/')
            print("Vue Path:", vue_path)  # Debugging output for the constructed path
            
            # Create a consistent component name from the file name
            component_name = os.path.splitext(os.path.basename(component_key))[0]
            component_name_camel = ''.join(word.capitalize() for word in component_name.split('_'))
            component_names.append(component_name_camel)

            # Add the component to the definitions using httpVueLoader
            component_js_definitions.append(
                f"'{component_name_camel}': httpVueLoader('{vue_path}')"
            )

    # Check if component names are populated
    print("Component Names:", component_names)  # Debugging output

    vue_loader = f"""
    <script src="https://cdn.jsdelivr.net/npm/vue@2/dist/vue.js"></script>
    <script src="https://cdn.jsdelivr.net/gh/FranckFreiburger/http-vue-loader/src/httpVueLoader.js"></script>
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        const app = new Vue({{
            el: '#app',
            data: {{
                activeComponents: [{', '.join([f"'{name}'" for name in component_names])}]
            }},
            components: {{
                {', '.join(component_js_definitions)}
            }},
            template: `
            <div>
                <component v-for="component in activeComponents" :is="component" :key="component"></component>
            </div>
            `
        }});
    }});
    </script>
    """

    # Load template HTML
    with open('index_template.html', 'r') as f:
        html_content = f.read()

    # Insert the Vue loader script into HTML content
    final_html = html_content.replace('</head>', f'{vue_loader}\n</head>')

    # Write the final HTML to index.html
    with open('index.html', 'w') as f:
        f.write(final_html)

    return final_html

if __name__ == "__main__":
    final_html = load_frontend_components()
    if (IGOOR_OUTPUT_HTML.lower() == 'true'):
        print(final_html)
    # Create a webview window in fullscreen mode
    if IGOOR_CLI.lower() != 'true':
        webview.create_window("IGOOR", "index.html", resizable=True) # fullscreen=True
        # Start the webview
        webview.start(debug=IGOOR_DEBUG.lower() == 'true')
        
