import rumps
from bambu_status import get_bambu_printer_status
import time
import os
import json
import logging
import subprocess # Import subprocess

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
# ---------------------------

# --- Configuration ---
# Default values if no saved state exists
DEFAULT_PRINTER_IP = ""
DEFAULT_PRINTER_SERIAL = ""
DEFAULT_PRINTER_ACCESS_CODE = ""
UPDATE_INTERVAL_SECONDS = 60 # Check every 60 seconds
# State file in user's home directory
STATE_FILE = os.path.expanduser("~/.bambu_status_app_state.json")
# ---------------------


class BambuStatusApp(rumps.App):
    def __init__(self):
        super(BambuStatusApp, self).__init__("3D Bambu", icon=None, quit_button=None)
        self.config_loaded = False
        self.printer_ip = DEFAULT_PRINTER_IP
        self.printer_serial = DEFAULT_PRINTER_SERIAL
        self.printer_access_code = DEFAULT_PRINTER_ACCESS_CODE
        # Create separate menu items for each setting
        self.menu = [
            rumps.MenuItem("Set IP Address..."),
            rumps.MenuItem("Set Serial Number..."),
            rumps.MenuItem("Set Access Code..."),
            None,
            rumps.MenuItem("Quit", callback=rumps.quit_application)
        ]
        self.title = "3D ❓ Login needed" # Default title
        # Create timer manually
        self.status_timer = rumps.Timer(self.update_status, UPDATE_INTERVAL_SECONDS)
        logging.info("App initializing...")
        self.load_settings() # Call load settings after initialization

    def _check_config_and_update(self):
        """Checks if all settings are present and updates config_loaded flag."""
        if self.printer_ip and self.printer_serial and self.printer_access_code:
            if not self.config_loaded:
                logging.info("All settings present. Enabling status updates via timer.")
                self.config_loaded = True
                self.title = "3D Bambu: Ready"
                self.status_timer.start() # Start timer when config is ready
            # If already loaded, do nothing, timer should be running
        else:
            if self.config_loaded: # Log only if state changes to not configured
                logging.info("Settings incomplete. Disabling status updates.")
                self.status_timer.stop() # Stop timer if config becomes incomplete
            self.config_loaded = False
            self.title = "3D ❓ Login needed"

    def load_settings(self):
        logging.info(f"Attempting to load settings from {STATE_FILE}")
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r') as f:
                    loaded_state = json.load(f)
                    logging.debug(f"Read state: {loaded_state}")
                    ip = loaded_state.get("printer_ip")
                    serial = loaded_state.get("printer_serial")
                    code = loaded_state.get("printer_access_code")

                    self.printer_ip = ip or DEFAULT_PRINTER_IP
                    self.printer_serial = serial or DEFAULT_PRINTER_SERIAL
                    self.printer_access_code = code or DEFAULT_PRINTER_ACCESS_CODE

                    # Check config status AFTER assigning values
                    self._check_config_and_update()
                    if self.config_loaded:
                        logging.info(f"Loaded valid saved settings from {STATE_FILE}.")
                        # Timer is started by _check_config_and_update
                    else:
                         logging.info("Loaded settings file, but configuration is incomplete.")
                    return # Exit load_settings

            logging.info("No valid/complete saved settings found, requiring login.")
            self._set_defaults_and_require_login()

        except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
            logging.error(f"Error loading settings from {STATE_FILE}: {e}", exc_info=True)
            self._set_defaults_and_require_login()

    def _set_defaults_and_require_login(self):
        self.printer_ip = DEFAULT_PRINTER_IP
        self.printer_serial = DEFAULT_PRINTER_SERIAL
        self.printer_access_code = DEFAULT_PRINTER_ACCESS_CODE
        self.status_timer.stop() # Ensure timer is stopped
        self.config_loaded = False
        self.title = "3D ❓ Login needed"

    def save_settings(self):
        state_to_save = {
            "printer_ip": self.printer_ip,
            "printer_serial": self.printer_serial,
            "printer_access_code": self.printer_access_code
        }
        logging.info(f"Attempting to save settings to {STATE_FILE}")
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(state_to_save, f, indent=4)
            logging.info(f"Settings saved successfully.")
        except IOError as e:
            logging.error(f"Error saving settings to {STATE_FILE}: {e}", exc_info=True)
            rumps.alert(title="Save Error", message=f"Could not save settings.\n{e}")

    def _run_applescript_input(self, prompt: str, title: str, default_answer: str) -> str | None:
        """Uses AppleScript to prompt user for input. Returns input or None if cancelled/error."""
        script = f'''
tell app "System Events"
    activate
    try
        display dialog "{prompt}" default answer "{default_answer}" with title "{title}" buttons {{"Cancel", "OK"}} default button "OK"
        set theResponse to text returned of the result
    on error number -128 # User cancelled
        return "__CANCEL__"
    end try
end tell
return theResponse
'''
        logging.info(f"Running AppleScript prompt: {title}")
        try:
            process = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                check=False # Don't raise exception on non-zero exit (e.g., cancel)
            )
            logging.info(f"AppleScript finished. Return code: {process.returncode}")

            if process.returncode == 0:
                user_input = process.stdout.strip()
                logging.info(f"AppleScript returned input: '{user_input[:20]}...'") # Log truncated input
                return user_input
            elif "__CANCEL__" in process.stderr: # Check stderr for our cancel signal
                logging.info("User cancelled AppleScript dialog.")
                return None
            else:
                logging.error(f"AppleScript error. stderr: {process.stderr.strip()}")
                rumps.alert(title="AppleScript Error", message="Could not get input.")
                return None

        except FileNotFoundError:
            logging.error("'osascript' command not found. Is AppleScript installed?")
            rumps.alert(title="Error", message="Cannot find 'osascript' command.")
            return None
        except Exception as e:
            logging.error(f"Error running AppleScript: {e}", exc_info=True)
            rumps.alert(title="Error", message="An unexpected error occurred while getting input.")
            return None

    @rumps.clicked("Set IP Address...")
    def set_ip_address(self, _):
        logging.info("'Set IP Address...' clicked.")
        self.status_timer.stop() # Stop timer before showing dialog
        logging.info("Status timer stopped for IP input.")
        new_val = None
        try:
            new_val = self._run_applescript_input(
                prompt="Enter Printer IP Address:",
                title="Set IP Address",
                default_answer=self.printer_ip
            )

            if new_val is not None: # Proceed only if user didn't cancel
                if new_val: # Check if input is not empty
                    self.printer_ip = new_val
                    logging.info("IP Address updated.")
                    self.save_settings()
                    self._check_config_and_update() # Check config
                else:
                    logging.warning("IP Address input was empty.")
                    rumps.alert(title="Input Error", message="IP Address cannot be empty.")
            # If new_val is None, user cancelled, do nothing further

        except Exception as e:
             # Errors during AppleScript execution are caught in _run_applescript_input
             # This catches potential errors in the processing logic *after* getting input
             logging.error(f"Error processing IP Address input: {e}", exc_info=True)
        finally:
            # Restart timer ONLY if config is loaded
            if self.config_loaded:
                self.status_timer.start()
                logging.info("Status timer restarted after IP input attempt.")
            else:
                 logging.info("Status timer remains stopped (config incomplete) after IP input attempt." )

    @rumps.clicked("Set Serial Number...")
    def set_serial_number(self, _):
        logging.info("'Set Serial Number...' clicked.")
        self.status_timer.stop()
        logging.info("Status timer stopped for Serial input.")
        new_val = None
        try:
            new_val = self._run_applescript_input(
                prompt="Enter Printer Serial Number:",
                title="Set Serial Number",
                default_answer=self.printer_serial
            )

            if new_val is not None:
                if new_val:
                    self.printer_serial = new_val
                    logging.info("Serial Number updated.")
                    self.save_settings()
                    self._check_config_and_update()
                else:
                    logging.warning("Serial Number input was empty.")
                    rumps.alert(title="Input Error", message="Serial Number cannot be empty.")

        except Exception as e:
             logging.error(f"Error processing Serial Number input: {e}", exc_info=True)
        finally:
            if self.config_loaded:
                self.status_timer.start()
                logging.info("Status timer restarted after Serial input attempt.")
            else:
                 logging.info("Status timer remains stopped (config incomplete) after Serial input attempt." )

    @rumps.clicked("Set Access Code...")
    def set_access_code(self, _):
        logging.info("'Set Access Code...' clicked.")
        self.status_timer.stop()
        logging.info("Status timer stopped for Access Code input.")
        new_val = None
        try:
            new_val = self._run_applescript_input(
                prompt="Enter Printer Access Code:",
                title="Set Access Code",
                default_answer=self.printer_access_code
            )

            if new_val is not None:
                if new_val:
                    self.printer_access_code = new_val
                    logging.info("Access Code updated.")
                    self.save_settings()
                    self._check_config_and_update()
                else:
                    logging.warning("Access Code input was empty.")
                    rumps.alert(title="Input Error", message="Access Code cannot be empty.")

        except Exception as e:
             logging.error(f"Error processing Access Code input: {e}", exc_info=True)
        finally:
            if self.config_loaded:
                self.status_timer.start()
                logging.info("Status timer restarted after Access Code input attempt.")
            else:
                 logging.info("Status timer remains stopped (config incomplete) after Access Code input attempt." )

    def update_status(self, _):
        if not self.config_loaded:
             if self.title != "3D ❓ Login needed":
                 logging.warning("update_status called but config not loaded.")
             self.title = "3D ❓ Login needed"
             return

        logging.info(f"Fetching status for {self.printer_ip}...")
        try:
            status_str = get_bambu_printer_status(
                self.printer_ip, self.printer_serial, self.printer_access_code, timeout=10
            )
            logging.debug(f"Raw status string received: {status_str}")
            if status_str == "Done":
                self.title = f"3D ✅ {status_str}"
            elif status_str == "Unknown":
                 self.title = f"3D ❓ {status_str}"
            elif "minutes" in status_str or "h" in status_str:
                 self.title = f"3D ⏳ {status_str}"
            else:
                 self.title = f"3D ℹ️ {status_str}"
            logging.info(f"Update successful: {self.title}")

        except Exception as e:
            logging.error(f"Error updating status: {e}", exc_info=True)
            self.title = "3D Bambu: Error"

# Set the app name for saving state correctly BEFORE instantiation
# BambuStatusApp.application_support = "BambuStatusMenuApp" # No longer needed for state

if __name__ == "__main__":
    logging.info("Starting Bambu Status Menu App...")
    app = BambuStatusApp()
    app.run() 