"""Protocol constants shared by the Bloomin8 modules."""

BLE_WAKE_CHARACTERISTIC_UUID = "0000f001-0000-1000-8000-00805f9b34fb"
BLE_WAKE_PAYLOAD_ON = b"\x01"
BLE_WAKE_PAYLOAD_OFF = b"\x00"
BLE_WAKE_PULSE_GAP_SECONDS = 0.001
STATE_READY_DELAY_SECONDS = 10
STATE_READY_TIMEOUT_SECONDS = 150
STATE_READY_STATUS_RETURN_CODES = (0, 100) #(0=Blank return after wake up (but is ready),100= Ready)
SHOW_RETRY_ATTEMPTS = 3
HTTP_REQUEST_TIMEOUT_SECONDS = 10
HTTP_UPLOAD_TIMEOUT_SECONDS = 45

"""Default settings values for the Bloomin8 modules."""
DEFAULT_MANAGED_GALLERIES = ("temp",)
DEFAULT_DISPLAY_MODE = "cover"
DEFAULT_ONLY_IF_IDLE = False

# deviceInfo also reports volatile values (battery, wifi...), so only the fields a restore
# replays can decide whether two states are the same.
RESTORE_STATE_KEYS = (
    "image",
    "gallery",
    "play_type",
    "dither",
    "saturation",
    "gamma",
    "play_duration",
    "playlist",
)