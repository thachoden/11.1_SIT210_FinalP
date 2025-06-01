import paho.mqtt.client as mqtt
import sys
import tkinter as tk
import threading
import time
import requests

# Define the MQTT broker details
broker = "broker.emqx.io"
port = 1883
topic_sensor_data = "task11.1/sensorData"
topic_led_state = "task11.1/ledStateData"
topic_led_brightness = "task11.1/ledBrightnessData"
topic_led_command = "task11.1/ledStateChangeCommand"
topic_led_value_command = "task11.1/ledValueCommand"
topic_sensor_status = "task11.1/sensorStatus"
topic_motion_sensor_status = "task11.1/motionSensorStatus"  
cBrightness = 0
controls_enabled = True  # Flag to track if controls are enabled

# Create the main Tkinter window
root = tk.Tk()
root.title("MQTT Sensor Data")

# Create labels to display lux value, LED state, and brightness
lux_label = tk.Label(root, text="Lux Value: N/A", font=("Helvetica", 16))
lux_label.pack(pady=10)

sensor_status_label = tk.Label(root, text="Light Sensor Status: N/A", font=("Helvetica", 16))
sensor_status_label.pack(pady=10)

# Add label to display motion sensor status
motion_sensor_status_label = tk.Label(root, text="Motion Sensor Status: N/A", font=("Helvetica", 16))
motion_sensor_status_label.pack(pady=10)

led_label = tk.Label(root, text="LED State: N/A", font=("Helvetica", 16))
led_label.pack(pady=10)

brightness_label = tk.Label(root, text="Brightness Value: N/A", font=("Helvetica", 16))
brightness_label.pack(pady=10)

# Create a frame to hold the slider and button
slider_frame = tk.Frame(root)
slider_frame.pack(pady=10)

# Create a slider to set LED value
led_value_slider = tk.Scale(slider_frame, from_=0, to=100, orient=tk.HORIZONTAL, label="Set LED Value", length=300)
led_value_slider.pack(side=tk.LEFT, padx=(20, 10))

# Create a button to send the LED value
def set_led_value():
    global controls_enabled
    led_value = led_value_slider.get()  # Get the value from the slider
    client.publish(topic_led_value_command, led_value)  # Publish the value
    print(f"Published LED Value: {led_value}")  # For debugging
    disable_all_controls()
    controls_enabled = False
    threading.Thread(target=enable_all_controls_after_delay, daemon=True).start()

set_button = tk.Button(slider_frame, text="Set LED Value", command=set_led_value)
set_button.pack(side=tk.BOTTOM, padx=(10, 20))

# Initial LED state
led_state = False

# Callback function to handle sensor data messages
def on_sensor_data(client, userdata, message):
    lux_value = message.payload.decode()
    lux_label.config(text=f"Lux Value: {lux_value}")

# Callback function to handle LED state messages
def on_led_state(client, userdata, message):
    global led_state
    led_state = message.payload.decode() == "1"
    led_label.config(text=f"LED State: {'ON' if led_state else 'OFF'}")
    led_label.config(bg='green' if led_state else 'red')
    toggle_button.config(text=f"Turn {'OFF' if led_state else 'ON'}")
    toggle_button.config(bg='red' if led_state else 'green')

# Callback function to handle LED brightness messages
def on_led_brightness(client, userdata, message):
    global cBrightness
    brightness_value = int(message.payload.decode())
    cBrightness = brightness_value
    brightness_label.config(text=f"Brightness Value: {brightness_value}")
    print(f"Received LED Brightness: {brightness_value}")

def on_sensor_status(client, userdata, message):
    status = message.payload.decode()
    if status == "OK":
        sensor_status_label.config(text="Light Sensor Status: Working", bg="green")
    else:
        sensor_status_label.config(text="Light Sensor Status: ERROR - Check Sensor", bg="red")

# Callback to handle motion sensor status messages
def on_motion_sensor_status(client, userdata, message):
    status = message.payload.decode()
    if status == "OK":
        motion_sensor_status_label.config(text="Motion Sensor Status: Working", bg="green")
    else:
        motion_sensor_status_label.config(text="Motion Sensor Status: Warning - Check Sensor", bg="yellow")

# Function to disable all controls
def disable_all_controls():
    set_button.config(state=tk.DISABLED)
    toggle_button.config(state=tk.DISABLED)
    led_value_slider.config(state=tk.DISABLED)

# Function to enable all controls
def enable_all_controls():
        set_button.config(state=tk.NORMAL)
        toggle_button.config(state=tk.NORMAL)
        led_value_slider.config(state=tk.NORMAL)
def enable_all_controls_after_delay():
    time.sleep(20)
    controls_enabled = True
    root.after(0, enable_all_controls) 
    client.subscribe(topic_led_state)
    led_value_slider.set(cBrightness)


# Function to toggle LED state and publish the new value
def toggle_led():
    client.unsubscribe(topic_led_state)
    global controls_enabled
    disable_all_controls()
    controls_enabled = False
    global led_state
    led_state = not led_state
    new_state = 1 if led_state else 0
    if not new_state:
        led_value_slider.set(0)
    
    led_label.config(text=f"LED State: {'ON' if led_state else 'OFF'}")
    led_label.config(bg='green' if led_state else 'red')
    toggle_button.config(bg='red' if led_state else 'green')
    toggle_button.config(text=f"Turn {'OFF' if led_state else 'ON'}")
    client.publish(topic_led_command, new_state)
    threading.Thread(target=enable_all_controls_after_delay, daemon=True).start()

# Create a button to toggle LED state
toggle_button = tk.Button(root, text="Toggle LED", command=toggle_led, width=15, height=1)
toggle_button.config(bg='green' if led_state else 'red')
toggle_button.pack(pady=20)

# Set up the MQTT client
client = mqtt.Client()
client.on_connect = lambda client, userdata, flags, rc: print("Connected with result code " + str(rc))
client.on_message = on_sensor_data
client.message_callback_add(topic_sensor_data, on_sensor_data)
client.message_callback_add(topic_led_state, on_led_state)
client.message_callback_add(topic_led_brightness, on_led_brightness)
client.message_callback_add(topic_sensor_status, on_sensor_status)
client.message_callback_add(topic_motion_sensor_status, on_motion_sensor_status)

# Handle disconnection
def on_disconnect(client, userdata, rc):
    print("Disconnected. Attempting to reconnect...")
    while not client.is_connected():
        try:
            client.reconnect()
            print("Reconnected successfully.")
        except Exception as e:
            print(f"Reconnect failed: {e}")
            time.sleep(5)  # Wait before retrying

# Connect to the broker
try:
    client.connect(broker, port)
    client.loop_start()
    client.subscribe(topic_sensor_data)
    client.subscribe(topic_led_state)
    client.subscribe(topic_led_brightness)
    client.subscribe(topic_sensor_status)
    client.subscribe(topic_motion_sensor_status) 
except Exception as e:
    print(f"Failed to connect to MQTT broker: {e}")

# Function to check internet connection status and enable/disable controls
def check_internet_connection():
    global controls_enabled
    try:
        response = requests.get("http://www.google.com", timeout=5)
        if response.status_code == 200:
            if controls_enabled:
                enable_all_controls()
        else:
            disable_all_controls()
            controls_enabled = True
    except requests.ConnectionError:
        disable_all_controls()
        controls_enabled = True
    except requests.Timeout:
        disable_all_controls()
        controls_enabled = True

    root.after(5000, check_internet_connection)  # Check again after 5 seconds

check_internet_connection()  # Start checking internet connection status
controls_enabled = True
# Start the Tkinter main loop
try:
    root.mainloop()
except KeyboardInterrupt:
    print("Exiting gracefully...")
    client.disconnect()
    sys.exit(0)
