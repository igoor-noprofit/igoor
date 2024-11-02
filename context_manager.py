class ContextManager:
    """
    A Singleton class to manage a shared context across the application.

    Context is dynamic and updated by plugins or vue components
    """
    _instance = None
    _context = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ContextManager, cls).__new__(cls)
            # Initialize the shared context
            cls._context = {
            }
        return cls._instance
    
    def update_context(self, key, value):
        """Update context with key-value pairs."""
        # print(f"Updating CONTEXT for {key} = {value}")
        self._context[key] = value

    def get_context(self):
        """Retrieve the entire context."""
        return self._context

    def get_value(self, key):
        """Retrieve a specific value from the context."""
        return self._context.get(key, None)

# Global access to the Singleton
context_manager = ContextManager()