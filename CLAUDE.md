# IGOOR Development Guide

## Build & Run Commands
- Install: `python -m venv venv && venv\scripts\activate && pip install -r requirements.txt`
- Run app: `python main.py` (debug mode) or `igoor.bat` (production mode)
- Test single test: `python tests/test_name.py` (e.g. `python tests/ffmpeg_check.py`)
- Update requirements: `pip freeze > requirements.txt`

## Code Style Guidelines
- Python: Version 3.10.6 required
- Plugin Structure: Each plugin has backend (.py) and frontend (.vue) components
- Backend Naming: Use lowercase_with_underscores for files, classes, methods and variables
- Logging: Use self.logger from Baseplugin for all logging (not print statements)
- Error Handling: Use try/except blocks with specific exceptions, use self.send_error_to_frontend() for UI errors
- Hooks: Use @hookimpl decorator for plugin manager hooks
- Database: Use self.db for database access, with proper error handling
- Frontend: Vue components use $_methodName for internal methods

## Communication
- Backend→Frontend: Use self.send_message_to_frontend()
- Plugin→Plugin: Use await self.pm.trigger_hook(hook_name="hook_name", **kwargs)
- Backend→App: Use await self.send_message_to_app()