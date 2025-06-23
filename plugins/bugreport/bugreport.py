from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl, PluginManager
from PIL import ImageGrab
from datetime import datetime
# Removed smtplib and email.message imports
import os, json
import logging # Keep this import for isinstance check
import shutil # Import shutil for file copying
from version import __appname__, __version__, __codename__

plugin_manager = PluginManager()

class Bugreport(Baseplugin):
    @hookimpl
    def startup(self):
        self.is_loaded = True
        # Ensure plugin_folder is set correctly if not done in base class
        if not hasattr(self, 'plugin_folder') or not self.plugin_folder:
            # Assuming plugin_manager or some config holds the base path
            # This might need adjustment based on your actual structure
            base_plugin_dir = os.path.join(os.getenv('APPDATA'), __appname__, 'plugins')
            self.plugin_folder = os.path.join(base_plugin_dir, self.__class__.__name__.lower())
            self.logger.info(f"Plugin folder explicitly set to: {self.plugin_folder}")


    def process_incoming_message(self, message):
        print("Received msg in BUGREPORT: " + message)
        self.logger.debug(f"Processing message in plugin bugreport: {message}")
        try:
            message_dict = json.loads(message)
            action = message_dict.get('action')

            if action == 'report_issue':
                console_log_data = message_dict.get('console_log', None)
                self.report_issue(console_log_data=console_log_data)
            elif action == 'add_comment': # Handle new action
                folder_path = message_dict.get('folder_path')
                comment = message_dict.get('comment')
                if folder_path and comment:
                    self.save_user_comment(folder_path, comment)
                else:
                    self.logger.error(f"Missing folder_path or comment for action 'add_comment': {message_dict}")
                    self.send_message_to_frontend({
                        "status": "error",
                        "action": "comment_saved", # Use same action for consistency in frontend handling
                        "message": "Missing required data (folder path or comment)."
                    })
            else:
                self.logger.debug(f"Unknown or unhandled action: {action}")
                # Optionally pass to base handler if needed for other actions
                # return super().process_incoming_message(message)

        except json.JSONDecodeError:
            self.logger.error(f"Failed to decode JSON from message: {message}")
            # Optionally pass non-JSON to base handler
            # return super().process_incoming_message(message)
        except Exception as e:
            self.logger.error(f"Error processing message in bugreport: {e}", exc_info=True)
            self.send_message_to_frontend({
                "status": "error",
                "message": f"Internal error processing request: {e}"
            })


    def take_screenshot(self, target_folder):
        """Takes a screenshot and saves it to the specified target folder."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Construct filename within the target folder
        screenshot_filename = os.path.join(target_folder, f'screenshot_{timestamp}.png')
        self.logger.info(f"Saving screenshot to {screenshot_filename}") # Use inherited logger
        try:
            img = ImageGrab.grab()
            img.save(screenshot_filename)
            return screenshot_filename
        except Exception as e:
            self.logger.error(f"Failed to take or save screenshot: {e}")
            return None # Return None on failure

    # Modify report_issue signature to accept console_log_data
    def report_issue(self, console_log_data=None):
        self.logger.info("Reporting issue locally...")

        # --- Create Timestamped Subfolder ---
        report_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Ensure self.plugin_folder is valid before joining
        if not hasattr(self, 'plugin_folder') or not self.plugin_folder or not os.path.isdir(self.plugin_folder):
            self.logger.error(f"Invalid or missing plugin_folder attribute: {getattr(self, 'plugin_folder', 'Not Set')}")
            self.send_message_to_frontend({"status": "error", "message": "Internal configuration error: Plugin folder not set."})
            return

        report_subfolder = os.path.join(self.plugin_folder, f'bugreport_{report_timestamp}')
        try:
            os.makedirs(report_subfolder, exist_ok=True) # Create folder, ignore if exists
            self.logger.info(f"Created report subfolder: {report_subfolder}")
        except OSError as e:
            self.logger.error(f"Failed to create report subfolder {report_subfolder}: {e}")
            # Send error back to frontend
            self.send_message_to_frontend({"status": "error", "message": "Failed to create report subfolder."})
            return # Stop processing

        # --- Take Screenshot (Save to Subfolder) ---
        screenshot_path = self.take_screenshot(report_subfolder) # Pass the subfolder path
        if not screenshot_path:
            # Error already logged in take_screenshot
            # Send error back to frontend
            self.send_message_to_frontend({"status": "error", "message": "Failed to save screenshot."})
            return # Stop processing
        self.logger.info(f"Screenshot saved to: {screenshot_path}")

        # --- Get Backend Log File Path ---
        log_path = None
        log_filename = None
        for handler in self.logger.handlers:
            if isinstance(handler, logging.FileHandler):
                log_path = handler.baseFilename
                log_filename = os.path.basename(log_path)
                self.logger.info(f"Found log file path: {log_path}")
                break

        # --- Copy Backend Log File to Subfolder ---
        log_copy_success = False
        if log_path and log_filename and os.path.exists(log_path):
            destination_log_path = os.path.join(report_subfolder, log_filename)
            try:
                shutil.copy2(log_path, destination_log_path)
                self.logger.info(f"Copied log file to: {destination_log_path}")
                log_copy_success = True
            except Exception as e:
                self.logger.error(f"Failed to copy log file from {log_path} to {destination_log_path}: {e}")
        elif log_path:
            self.logger.warning(f"Log file path found ({log_path}) but file does not exist. Cannot copy.")
        else:
            self.logger.warning("Could not find log file path to copy.") # Use inherited logger

        # --- Copy LLM Invocation Log File to Subfolder ---
        llm_log_copy_success = False
        if log_path: # Only proceed if we found the main log's directory
            log_dir = os.path.dirname(log_path)
            today_str = datetime.now().strftime('%Y%m%d')
            llm_log_filename = f"llm_invocations_{today_str}.jsonl"
            llm_log_path = os.path.join(log_dir, llm_log_filename)
            if os.path.exists(llm_log_path):
                destination_llm_log_path = os.path.join(report_subfolder, llm_log_filename)
                try:
                    shutil.copy2(llm_log_path, destination_llm_log_path)
                    self.logger.info(f"Copied LLM invocation log file to: {destination_llm_log_path}")
                    llm_log_copy_success = True
                except Exception as e:
                    self.logger.error(f"Failed to copy LLM invocation log file from {llm_log_path} to {destination_llm_log_path}: {e}")
            else:
                self.logger.warning(f"LLM invocation log file for today ({llm_log_filename}) not found in {log_dir}.")
        else:
            self.logger.warning("Cannot determine LLM invocation log directory because main log path was not found.")

        # --- Save Browser Console Log to Subfolder ---
        console_log_saved = False
        if console_log_data is not None:
            console_log_filename = "browser_console.log"
            destination_console_log_path = os.path.join(report_subfolder, console_log_filename)
            try:
                with open(destination_console_log_path, 'w', encoding='utf-8') as f:
                    f.write(console_log_data)
                self.logger.info(f"Saved browser console log to: {destination_console_log_path}")
                console_log_saved = True
            except Exception as e:
                self.logger.error(f"Failed to save browser console log to {destination_console_log_path}: {e}")
        else:
            self.logger.info("No browser console log data received from frontend.")


        # --- Send status message back to the frontend ---
        # smsg = self.lang
        status_message = f"Report saved in folder: {report_subfolder}"
        # Add details about missing files if necessary
        if not log_copy_success and log_path:
            status_message += " (Backend log could not be copied)."
        elif not log_path:
            status_message += " (Backend log not found)."
        if not console_log_saved and console_log_data is not None:
            status_message += " (Browser log could not be saved)."
        elif console_log_data is None:
            status_message += " (No browser log received)."
        # Add LLM log status
        if not llm_log_copy_success and log_path: # Check log_path again to avoid redundant message if main log wasn't found
            status_message += " (LLM log could not be copied/found)."
        elif not log_path:
             status_message += " (LLM log not searched)."


        self.send_message_to_frontend({
            "status": "success",
            "action": "report_saved",
            "message": status_message,
            "folder_path": report_subfolder # Ensure folder_path is sent
        })


    def save_user_comment(self, folder_path, comment):
        """Saves the user's comment to a text file in the specified folder."""
        self.logger.info(f"Attempting to save user comment to folder: {folder_path}")

        # --- Security Check: Ensure folder_path is within the plugin's directory ---
        # Resolve to absolute paths to prevent traversal issues like '../'
        try:
            # Ensure self.plugin_folder is valid
            if not hasattr(self, 'plugin_folder') or not self.plugin_folder or not os.path.isdir(self.plugin_folder):
                raise ValueError(f"Invalid or missing plugin_folder attribute: {getattr(self, 'plugin_folder', 'Not Set')}")

            base_dir = os.path.abspath(self.plugin_folder)
            target_dir = os.path.abspath(folder_path)

            # Check if the target directory starts with the base plugin directory path
            if not target_dir.startswith(base_dir):
                self.logger.error(f"Security Violation: Attempted to write comment outside plugin folder. Target: {target_dir}, Base: {base_dir}")
                self.send_message_to_frontend({
                    "status": "error",
                    "action": "comment_saved",
                    "message": "Invalid folder path specified."
                })
                return

            # Also check if the target directory actually exists
            if not os.path.isdir(target_dir):
                self.logger.error(f"Target folder for comment does not exist: {target_dir}")
                self.send_message_to_frontend({
                "status": "error",
                "action": "comment_saved",
                "message": "Report folder not found."
                })
                return

        except Exception as e:
            self.logger.error(f"Error during path validation for saving comment: {e}", exc_info=True)
            self.send_message_to_frontend({"status": "error", "action": "comment_saved", "message": f"Internal path validation error: {e}"})
            return


        # --- Write the comment to file ---
        comment_filename = "user_comment.txt"
        destination_comment_path = os.path.join(target_dir, comment_filename)

        try:
            with open(destination_comment_path, 'w', encoding='utf-8') as f:
                f.write(comment)
            self.logger.info(f"Saved user comment to: {destination_comment_path}")
            # Send success message
            self.send_message_to_frontend({
                "status": "success",
                "action": "comment_saved",
                "message": "Comment saved successfully."
            })
        except Exception as e:
            self.logger.error(f"Failed to save user comment to {destination_comment_path}: {e}")
            # Send error message
            self.send_message_to_frontend({
                "status": "error",
                "action": "comment_saved",
                "message": f"Failed to write comment file: {e}"
            })

        # Return value is less critical now that we send status via websocket
        # return status_message