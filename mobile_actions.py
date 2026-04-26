import logging
from ppadb.client import Client as AdbClient

log = logging.getLogger("jarvis.mobile")

class MobileController:
    def __init__(self, host="127.0.0.1", port=5037):
        self.host = host
        self.port = port
        self.client = None
        self.device = None

    def connect(self):
        try:
            self.client = AdbClient(host=self.host, port=self.port)
            devices = self.client.devices()
            if len(devices) > 0:
                self.device = devices[0]
                log.info(f"Connected to mobile device: {self.device.serial}")
                return True
            return False
        except Exception as e:
            log.error(f"Mobile connection failed: {e}")
            return False

    def answer_call(self):
        if not self.device: return "No device connected."
        # Keyevent 5 is CALL, 79 is Headset hook. Both are used to answer.
        self.device.shell("input keyevent 5")
        self.device.shell("input keyevent 79")
        return "Attempted to answer the call, sir."

    def open_app(self, package_name):
        if not self.device: return "No device connected."
        self.device.shell(f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1")
        return f"Opening {package_name} on your mobile, sir."

    def get_status(self):
        if not self.device: return "Disconnected"
        return f"Connected ({self.device.serial})"

mobile_controller = MobileController()
