from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
import json,socket,os,time
import psutil
import subprocess
import win32gui, win32com


class Extkeyb(Baseplugin):
    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name, pm)
        self.settings = self.get_my_settings()
        self.is_igoor_maximized = True
        self.keyb_type = self.settings.get("keyb_type","tabtip")
        self.ready = False
        # TABTIP on modern WINDOWS
        if (self.keyb_type == "tabtip"):
            self.app_exe = "TabTip.exe"
            self.app_path = os.path.join("C:\\Program Files\\Common Files\\microsoft shared\\ink\\",self.app_exe)            
            if (not os.path.exists(self.app_path)):
                self.logger.error(f"TabTip external keyboard not found at {self.app_path}")
                # COULD USE OSK HERE INSTEAD for older Windows versions
                # path C:\\Windows\\System32\\osk.exe
                return False
            self.ready = True
        # IGOOR OWN EXTERNAL KEYBOARD
        elif (self.keyb_type == "igoor"):
            self.app_exe = "IGOOR_OSK.exe"
            if (self.locate_igoor_app()):
                self.conn_host = self.settings.get("conn_host", "127.0.0.1")
                self.conn_port = self.settings.get("conn_port", 8765)
                self.socket = None
                self.ready = True
            else:
                self.logger.error("IGOOR external keyboard not found")
                return False
        else:
            self.logger.error(f"Unknown keyboard type {self.keyb_type}")
            return False
        if (self.ready):
            self.is_running = self.is_app_running(self.app_exe)
            if self.is_running:
                if (self.keyb_type == "igoor"):
                    self.connect()
            else:
                try:
                    # Launch the executable at self.exe_path
                    subprocess.Popen([self.app_path], shell=True)
                    self.is_running = True  # Update the flag after launching
                    # time.sleep(1) ?
                    if (self.keyb_type == "igoor"):
                        self.connect()
                except Exception as e:
                    self.logger.error(f"Failed to launch {self.exe_path}: {e}")
                    self.is_running = False
            
    def locate_igoor_app(self):
        install_path = os.path.join(self.appdata_path, self.app_name, "extkeyb-install-path.txt")
        self.logger.info(f"looking for {install_path}")
        if os.path.exists(install_path):
            with open(install_path, "r") as f:
                self.app_path = os.path.join(f.read().strip(),"IGOOR_OSK.exe")
            return True
        self.logger.error(f"IGOOR external keyboard not found in {install_path}")
        return False
    
    def is_app_running(self,app_name):
        for process in psutil.process_iter(['name']):
            if process.info['name'].lower() == app_name.lower():
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

    def is_tabtip_visible():
        hwnd = win32gui.FindWindow("IPTip_Main_Window", None)  # TabTip window class
        if hwnd:
            return win32gui.IsWindowVisible(hwnd)
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
        if (not self.is_app_running):
            if (self.keyb_type == "igoor"):
                self.send_command('show')   
            elif (self.keyb_type == "tabtip"):
                if (not self.is_tabtip_visible()):
                    self.show_virtual_keyboard()
                else:
                    print("TabTip already visible")
            else:
                self.logger.warning(f"Cannot show unsupported keyboard type {self.keyb_type}")
        else:
            print("Virtual keyboard already running")
    
    @hookimpl
    def hide_virtual_keyboard(self):
        if (self.is_app_running):
            if (self.keyb_type == "igoor"):
                self.connect()
            elif (self.keyb_type == "tabtip"):
                tip = win32com.client.Dispatch("TabletTip.InputPanel")
                hwnd = win32gui.GetForegroundWindow()  # or the window you want to attach to
                tip.Dismiss()  # hides the keyboard
            else:
                self.logger.warning(f"Cannot hide unsupported keyboard type {self.keyb_type}")
            self.send_command('hide')
        else:
            print("No need to hide, virtual keyboard already hidden")
    
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

