import webview
import os
import re
from plugin_manager import PluginManager
from dotenv import load_dotenv
load_dotenv()
from context_manager import ContextManager

context_manager = ContextManager()

# VARS HERE
IGOOR_DEBUG = os.getenv('IGOOR_DEBUG', 'False') 
IGOOR_CLI = os.getenv('IGOOR_CLI', 'False') 
IGOOR_OUTPUT_HTML = os.getenv('IGOOR_OUTPUT_HTML', 'False') 

def load_frontend_components():
    manager = PluginManager()
    plugins_metadata = manager.get_plugins_metadata()
    print("Plugins metadata:", plugins_metadata)  # Debugging output

    # Components organized by category
    components_by_category = {
        'topbar': [],
        'header': [],
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

    print(components_by_category)
    # Prepare Vue components registration
    vue_component_definitions = []
    for category, components in components_by_category.items():
        for component in components:
            vue_component_definitions.append(
                f"'{component['name']}': httpVueLoader('{component['path']}')"
            )

    vue_loader = f"""
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        const app = new Vue({{
            el: '#app',
            components: {{
                {', '.join(vue_component_definitions)}
            }},
            template: `
            <div>
                <header>
                    <div id="topbar">
                        { ''.join(f'<{comp["name"].lower()} />' for comp in components_by_category['topbar']) }
                    </div>
                    { ''.join(f'<{comp["name"].lower()} />' for comp in components_by_category['header']) }
                </header>
                <main>
                    { ''.join(f'<{comp["name"].lower()} />' for comp in components_by_category['main']) }
                </main>
                <footer>
                    { ''.join(f'<{comp["name"].lower()} />' for comp in components_by_category['footer']) }
                </header>
            </div>
            `
        }});
    }});
    </script>
    """

    # Load and modify the template HTML
    with open('index_template.html', 'r') as f:
        html_content = f.read()

    # Insert the Vue loader script into HTML content
    final_html = html_content.replace('</head>', f'{vue_loader}\n</head>')

    # Write the final HTML to index.html
    with open('index.html', 'w') as f:
        f.write(final_html)

    return final_html

def get_full_context():
    return context_manager.get_context()

if __name__ == "__main__":
    final_html = load_frontend_components()
    if (IGOOR_OUTPUT_HTML.lower() == 'true'):
        print(final_html)
    # Create a webview window in fullscreen mode
    if IGOOR_CLI.lower() != 'true':
        webview.create_window("IGOOR", "index.html", resizable=True) # fullscreen=True
        # Start the webview
        webview.start(debug=IGOOR_DEBUG.lower() == 'true')
    else:
        print(get_full_context())
        
