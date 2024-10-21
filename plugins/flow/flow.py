from plugin_manager import hookimpl 

class Flow:
    @hookimpl
    def get_frontend_components(self):
        print("loading flow frontend")
        return [
            {
                "vue": "flow_component.vue"
            }
        ]