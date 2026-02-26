from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
import json,socket,os,time
import psutil
import subprocess
import win32gui, win32con
from pywinauto import Application
from pywinauto.application import ProcessNotFoundError
from pywinauto.findwindows import ElementNotFoundError


class Extkeyb(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name, pm)
        self.settings = self.get_my_settings()
        self.is_igoor_maximized = True
        self.keyb_type = self.settings.get("keyb_type","osk")
        self.logger.info(f"Using external keyboard type {self.keyb_type}")
        # TABTIP on modern WINDOWS
        if (self.keyb_type == "tabtip"):
            self.app_exe = "TabTip.exe"
            self.app_path = os.path.join("C:\\Program Files\\Common Files\\microsoft shared\\ink\\",self.app_exe)      
            if (not os.path.exists(self.app_path)):
                self.logger.error(f"TabTip external keyboard not found at {self.app_path}")
                # COULD USE OSK HERE INSTEAD for older Windows versions
                # path C:\\Windows\\System32\\osk.exe
            self.mark_ready()
        # IGOOR OWN EXTERNAL KEYBOARD
        elif (self.keyb_type == "igoor"):
            self.app_exe = "IGOOR_OSK.exe"
            if (self.locate_igoor_app()):
                self.conn_host = self.settings.get("conn_host", "127.0.0.1")
                self.conn_port = self.settings.get("conn_port", 8765)
                self.socket = None
                self.mark_ready()
            else:
                self.logger.error("IGOOR external keyboard not found")
        elif (self.keyb_type == "osk"):
            self.app_exe = "osk.exe"
            self.app_path = os.path.join("C:\\Windows\\System32\\",self.app_exe)
            self.mark_ready()
        else:
            self.logger.error(f"Unknown keyboard type {self.keyb_type}")
        if (self.ready):
            self.logger.info("Trying to initialize virtual keyboard")
            self.is_running = self.is_app_running()
            if self.is_running:
                if (self.keyb_type == "igoor"):
                    self.connect()
            '''
            else:
                if (self.keyb_type == "tabtip" or self.keyb_type == "osk"):
                    if (self.start_process()):
                        self.is_running = True
            '''
            

   
    
    # TODO: RECHECK ENTIRE FUNCTION 
    def locate_igoor_app(self):
        install_path = os.path.join(self.appdata_path, self.app_name, "extkeyb-install-path.txt")
        self.logger.info(f"looking for {install_path}")
        if os.path.exists(install_path):
            with open(install_path, "r") as f:
                self.app_path = os.path.join(f.read().strip(),self.app_exe)
            return True
        self.logger.error(f"IGOOR external keyboard not found in {install_path}")
        return False
    
    # CHECK IF SELF.APP_EXE IS RUNNING
    def is_app_running(self):
        print(f"Checking if {self.app_exe} is running")
        for process in psutil.process_iter(['name']):
            if process.info['name'].lower() == self.app_exe.lower():
                print(f"{self.app_exe} is running with PID {process.pid}")
                return True
        return False
    
    def start_process(self):
        p = subprocess.Popen([self.app_path], shell=True)
        if (p and p.pid):
            self.logger.info(f"Started process {self.app_exe} with PID {p.pid}")
            return True
        else:
            self.logger.error(f"Failed to start {self.app_exe}")
            return False

    @hookimpl
    def startup(self):
        if(self.ready):
            if (self.keyb_type == "igoor"):
                self.connect()
        else:
            self.logger.warning("Virtual keyboard not ready at startup")

    def connect(self):
        max_retries = self.settings.get("conn_max_retries", 3)
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                self.socket = socket.create_connection((self.conn_host, self.conn_port))
                self.logger.info(f"Successfully connected on attempt {retry_count + 1}")
                return  # Exit successfully
            except ConnectionRefusedError:
                retry_count += 1
                self.logger.warning(f"Connection refused. Attempt {retry_count}/{max_retries}")
                if retry_count < max_retries:
                    self.logger.warning("Retrying...")
                    # Optional: add a small delay between retries
                    import time
                    time.sleep(1)
                else:
                    self.logger.error("Max retries reached. Connection failed.")
                    # Handle final failure case
                    break

    @hookimpl
    def igoor_is_minimized(self):
        print("igoor is not active")
        self.hide_virtual_keyboard()
        self.is_igoor_maximized = False
    
    '''    
    @hookimpl
    def igoor_is_maximized(self):
        print("igoor is active")
        self.is_igoor_maximized = True
    ''' 
    @hookimpl
    async def change_view(self,lastview,currentview):
        print(f"change view {lastview} {currentview}")
        if currentview == "autocomplete":
            self.show_virtual_keyboard()
        else:
            self.hide_virtual_keyboard()
        
    @hookimpl
    def show_virtual_keyboard(self):
        if (self.keyb_type == "igoor"):
            self.send_command('show')   
        elif (self.keyb_type == "osk"):
            self.start_process()
        elif (self.keyb_type == "tabtip"):
            if (self.show_tabtip()):
                return True
            else:
                if (not self.is_app_running()):
                    if (self.start_process()):
                        print("Started TabTip")
                        if (self.show_tabtip()):
                            return True
                        else:
                            self.logger.error("TabTip running but failed to show")
                            return False
                    else:
                        self.logger.error("Failed to start TabTip process")
                        return False
        else:
            self.logger.warning(f"Cannot show unsupported keyboard type {self.keyb_type}")
            return False

    
    @hookimpl
    def hide_virtual_keyboard(self):
        if (self.is_app_running()):
            if (self.keyb_type == "igoor"):
                self.connect()
            elif (self.keyb_type == "osk"):
                # COULD TRY TASKKILL
                # try:
                #    subprocess.run(["taskkill", "/IM", "osk.exe"], check=True)
                # except subprocess.CalledProcessError as e:
                #    print("Failed:", e)
                # Connect to OSK
                return self.close_osk() 
            elif (self.keyb_type == "tabtip"):
                if (self.hide_tabtip()):
                    return True
                if (not self.is_app_running()):
                    self.logger.info("TabTip already closed")
                    return True
                else:
                    # COULD TRY TASKKILL    
                    self.logger.error("TabTip running but failed to hide")
                    return False
            else:
                self.logger.warning(f"Cannot hide unsupported keyboard type {self.keyb_type}")
            self.send_command('hide')
        else:
            print("No need to hide, virtual keyboard already hidden")
    
    def close_osk(self):
        try:
            app = Application(backend="uia").connect(path=self.app_exe, timeout=2)
            window = app.window(class_name="OSKMainClass")
            window.close()
            window.wait_not_visible(timeout=3)
            self.logger.info("Closed OSK via UIAutomation")
            return True
        except (ProcessNotFoundError, ElementNotFoundError):
            self.logger.info("OSK window not found via UIAutomation, trying fallbacks")
        except Exception as e:
            self.logger.warning(f"UIAutomation failed to close OSK: {e}")

        try:
            hwnd = win32gui.FindWindow("OSKMainClass", None)
            if hwnd:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                self.logger.info("Sent WM_CLOSE to OSK")
                return True
            else:
                self.logger.info("OSK window not found for WM_CLOSE fallback")
        except Exception as e:
            self.logger.warning(f"Failed to send WM_CLOSE to OSK: {e}")

        return self._terminate_osk_process()

    def _terminate_osk_process(self):
        for process in psutil.process_iter(["pid", "name"]):
            if process.info["name"] and process.info["name"].lower() == self.app_exe.lower():
                try:
                    process.terminate()
                    process.wait(timeout=3)
                    self.logger.info(f"Terminated {self.app_exe} (PID {process.pid})")
                    return True
                except (psutil.TimeoutExpired, psutil.AccessDenied):
                    try:
                        process.kill()
                        process.wait(timeout=3)
                        self.logger.info(f"Force killed {self.app_exe} (PID {process.pid})")
                        return True
                    except Exception as kill_error:
                        self.logger.error(f"Failed to force kill {self.app_exe} (PID {process.pid}): {kill_error}")
                        return False
                except psutil.NoSuchProcess:
                    return True
        self.logger.info(f"No running {self.app_exe} process found while closing")
        return True
    
    def send_command(self, cmd):    
        if self.socket is None:
            self.logger.warning("Socket not connected.")
            return False
        self.logger.info(f"sending command {cmd}")    
        try:
            message = json.dumps({"action": cmd}) + '\n'
            self.socket.sendall(message.encode())
            response = self.socket.recv(1024).decode()
            self.logger.info("response {response}")
            return response
        except (ConnectionResetError, BrokenPipeError, OSError):
            self.logger.warning("Connection lost. Reconnecting...")
            # Reconnect and retry once
            self.connect()
            message = json.dumps({"action": cmd}) + '\n'
            self.socket.sendall(message.encode())
            return self.socket.recv(1024).decode()

    # TABTIP SPECIFIC METHODS
    def is_tabtip_visible(self):
        try:
            hwnd = win32gui.FindWindow("IPTip_Main_Window", None)  # TabTip window class
            if hwnd:
                return win32gui.IsWindowVisible(hwnd)
            return False
        except Exception as e:
            self.logger.error(f"Exception trying to check tabtip visibility: {e}")
            return False

    def show_tabtip(self):
        try:
            print("Trying to show TabTip")
            if (self.is_tabtip_visible()):
                print("TabTip already visible")
                return True
            else:
                print("TabTip not visible, trying to show")
                hwnd = win32gui.FindWindow("IPTip_Main_Window", None)
                if hwnd:
                    print("Found TabTip window, showing it")
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                else:
                    print("TabTip window not found")
                    return False
                return True
        except Exception as e:
            self.logger.error(f"Exception trying to show tabtip: {e}")
            return False
        
    def hide_tabtip(self):
        try:
            hwnd = win32gui.FindWindow("IPTip_Main_Window", None)
            if hwnd:
                win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
            return True
        except Exception as e:
            self.logger.error(f"Exception trying to hide tabtip: {e}")
            return False
