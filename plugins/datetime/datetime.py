from plugin_manager import hookimpl 

class Datetime:
    @hookimpl
    def get_frontend_components(self):
        print("loading datetime frontend")
        return [
            {
                "vue": "datetime_component.vue"
            }
        ]