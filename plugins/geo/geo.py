from plugin_manager import hookimpl 

class Geo:
    @hookimpl
    def get_frontend_components(self):
        print("loading geo frontend")
        return [
            {
                "vue": "geo_component.vue"
            }
        ]