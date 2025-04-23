import paho.mqtt.client as mqtt
import ssl
import json
import time
import uuid
import threading

def get_bambu_printer_status(ip: str, serial: str, access_code: str, timeout: int = 10) -> str:
    """
    Connects to a Bambu Lab printer via MQTTs and retrieves its status,
    returning a formatted string indicating the print progress.

    Args:
        ip: The IP address of the printer.
        serial: The serial number of the printer.
        access_code: The access code for the printer.
        timeout: Time in seconds to wait for a status message.

    Returns:
        A string: "Done", "X minutes remaining", or "Unknown".
    """
    client_id = f"bambu-status-checker-{uuid.uuid4()}"
    mqtt_port = 8883
    publish_topic = f"device/{serial}/request"
    subscribe_topic = f"device/{serial}/report"
    status_payload = {"pushing": {"sequence_id": "0", "command": "pushall"}}

    status_data = None
    message_received_event = threading.Event()
    connection_error = None

    def on_connect(client, userdata, flags, rc, properties=None):
        nonlocal connection_error
        if rc == 0:
            # print("Connected to MQTT Broker!") # Silenced verbose output
            client.subscribe(subscribe_topic)
            client.publish(publish_topic, json.dumps(status_payload))
        else:
            connection_error = f"Failed to connect, return code {rc}"
            # print(connection_error) # Silenced verbose output
            message_received_event.set() # Signal to stop waiting

    def on_message(client, userdata, msg):
        nonlocal status_data
        # print(f"Received message on {msg.topic}") # Silenced verbose output
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            # Check if it looks like a status message (often contains 'print')
            if "print" in payload:
                status_data = payload
                # print("Status data received.") # Silenced verbose output
                message_received_event.set()
            # Ignore other message types like pushing echo
        except json.JSONDecodeError:
            print("Failed to decode JSON message") # Keep critical errors visible
        except Exception as e:
            print(f"Error processing message: {e}") # Keep critical errors visible


    def on_disconnect(client, userdata, rc, properties=None):
        # print(f"Disconnected with result code {rc}") # Silenced verbose output
        pass

    def on_connect_fail(client, userdata):
        nonlocal connection_error
        connection_error = "MQTT connection failed."
        # print(connection_error) # Silenced verbose output
        message_received_event.set() # Signal to stop waiting


    client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.on_connect_fail = on_connect_fail


    client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT, cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True) # Bambu printers often use self-signed certs
    client.username_pw_set("bblp", password=access_code)

    try:
        client.connect_async(ip, mqtt_port, 60)
        client.loop_start()

        # print(f"Waiting for status message for up to {timeout} seconds...") # Silenced verbose output
        event_triggered = message_received_event.wait(timeout=timeout)

    finally: # Ensure cleanup happens
        client.loop_stop()
        client.disconnect()

    if connection_error:
         # print(f"Exiting due to connection error: {connection_error}") # Silenced verbose output
         return "Unknown" # Return "Unknown" on connection error
    elif not event_triggered:
        # print("Timeout waiting for status message.") # Silenced verbose output
        return "Unknown" # Return "Unknown" on timeout
    elif status_data:
        # print("Successfully retrieved status.") # Silenced verbose output
        # Parse the status
        print_data = status_data.get("print", {})
        remaining_time = print_data.get("mc_remaining_time", -1) # In minutes
        gcode_state = print_data.get("gcode_state", "")

        if gcode_state in ["FINISH", "FAILED", "IDLE"] or (gcode_state == "RUNNING" and remaining_time == 0) :
             return "Done"
        elif remaining_time > 0 and gcode_state == "RUNNING":
            hours = remaining_time // 60
            minutes = remaining_time % 60
            if hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes} minutes"
        else:
            # Fallback for unexpected states or missing time while not finished
            return "Unknown"
    else:
         # print("No status data received, though connection seemed okay.") # Silenced verbose output
         return "Unknown" # Return "Unknown" if no data received


if __name__ == "__main__":
    # Printer details are already set from previous step
    PRINTER_IP = "192.168.68.113"
    PRINTER_SERIAL = "03919D4C0708643"
    PRINTER_ACCESS_CODE = "36791889"

    # Get the formatted status string
    status_string = get_bambu_printer_status(PRINTER_IP, PRINTER_SERIAL, PRINTER_ACCESS_CODE)

    # Print the result
    print(f"Printer Status: {status_string}") 