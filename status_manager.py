# status_manager.py
class StatusManager:
    # Singleton instance
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(StatusManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._status = "online"  # Default status
            self._observers = []
            self._initialized = True

    def register_observer(self, observer):
        if observer not in self._observers:
            self._observers.append(observer)

    def unregister_observer(self, observer):
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_observers(self):
        for observer in self._observers:
            observer.update_status(self._status)

    def set_status(self, status):
        if status != self._status:
            print(f"Status changing from {self._status} to {status}")
            self._status = status
            self.notify_observers()

    def get_status(self):
        return self._status