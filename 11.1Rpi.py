import paho.mqtt.client as mqtt
import sys
import tkinter as tk
import tkinter.simpledialog as simpledialog
import tkinter.messagebox as messagebox
import threading
import time
import requests

broker = "broker.emqx.io"
port = 1883

class SensorGUI:
  def __init__(self, parent, client, sensor_id):
      self.client = client
      self.sensor_id = sensor_id
      self.cBrightness = 0
      self.controls_enabled = True
      self.led_state = False

      # Topics specific to sensor_id
      self.topic_sensor_data = f"task11.1/sensorData/{sensor_id}"
      self.topic_led_state = f"task11.1/ledStateData/{sensor_id}"
      self.topic_led_brightness = f"task11.1/ledBrightnessData/{sensor_id}"
      self.topic_led_command = f"task11.1/ledStateChangeCommand/{sensor_id}"
      self.topic_led_value_command = f"task11.1/ledValueCommand/{sensor_id}"
      self.topic_light_sensor = f"task11.1/sensorStatus/{sensor_id}"
      self.topic_motion_sensor = f"task11.1/motionSensorStatus/{sensor_id}"

      # Frame containing this GUI
      self.frame = tk.Frame(parent, bd=2, relief=tk.SUNKEN, padx=10, pady=10)
      self.frame.pack(pady=10, fill=tk.X)

      self.title_label = tk.Label(self.frame, text=f"Sensor ID: {sensor_id}", font=("Helvetica", 14, "bold"))
      self.title_label.pack()

      self.lux_label = tk.Label(self.frame, text="Lux Value: N/A", font=("Helvetica", 16))
      self.lux_label.pack(pady=5)

      self.led_label = tk.Label(self.frame, text="LED State: N/A", font=("Helvetica", 16))
      self.led_label.pack(pady=5)
      
      self.sensor_status_label = tk.Label(self.frame, text="Light Sensor Status: N/A", font=("Helvetica", 16))
      self.sensor_status_label.pack(pady=10)

      # Add label to display motion sensor status
      self.motion_sensor_status_label = tk.Label(self.frame, text="Motion Sensor Status: N/A", font=("Helvetica", 16))
      self.motion_sensor_status_label.pack(pady=10)

      self.brightness_label = tk.Label(self.frame, text="Brightness Value: N/A", font=("Helvetica", 16))
      self.brightness_label.pack(pady=5)

      slider_frame = tk.Frame(self.frame)
      slider_frame.pack(pady=5)

      self.led_value_slider = tk.Scale(slider_frame, from_=0, to=100, orient=tk.HORIZONTAL, label="Set LED Value", length=300)
      self.led_value_slider.pack(side=tk.LEFT, padx=(20,10))

      self.set_button = tk.Button(slider_frame, text="Set LED Value", command=self.set_led_value)
      self.set_button.pack(side=tk.LEFT, padx=(10,20))

      self.toggle_button = tk.Button(self.frame, text="Toggle LED", command=self.toggle_led, width=15, height=1)
      self.toggle_button.config(bg='green' if self.led_state else 'red')
      self.toggle_button.pack(pady=10)

      # Subscribe to topics - do this after client is connected
      self.subscribe_to_topics()
  
  def subscribe_to_topics(self):
      """Subscribe to all topics for this sensor"""
      if hasattr(self.client, 'connected_flag') and self.client.connected_flag:
          print(f"Subscribing to topics for sensor {self.sensor_id}")
          self.client.subscribe(self.topic_sensor_data)
          self.client.subscribe(self.topic_led_state)
          self.client.subscribe(self.topic_led_brightness)
          self.client.subscribe(self.topic_light_sensor)
          self.client.subscribe(self.topic_motion_sensor)
      else:
          print(f"Client not connected, will subscribe later for sensor {self.sensor_id}")
  
  def on_sensor_status(self, client, userdata, message):
      status = message.payload.decode()
      print(f"Received light sensor status for {self.sensor_id}: {status}")
      if status == "OK":
          self.sensor_status_label.config(text="Light Sensor Status: Working", bg="green")
      else:
          self.sensor_status_label.config(text="Light Sensor Status: ERROR - Check Sensor", bg="red")

  # Callback to handle motion sensor status messages
  def on_motion_sensor_status(self, client, userdata, message):
      status = message.payload.decode()
      print(f"Received motion sensor status for {self.sensor_id}: {status}")
      if status == "OK":
          self.motion_sensor_status_label.config(text="Motion Sensor Status: Working", bg="green")
      else:
          self.motion_sensor_status_label.config(text="Motion Sensor Status: Warning - Check Sensor", bg="yellow")
  
  def on_sensor_data(self, client, userdata, message):
      lux_value = message.payload.decode()
      print(f"Received sensor data for {self.sensor_id}: {lux_value}")
      self.lux_label.config(text=f"Lux Value: {lux_value}")

  def on_led_state(self, client, userdata, message):
      self.led_state = message.payload.decode() == "1"
      print(f"Received LED state for {self.sensor_id}: {self.led_state}")
      self.led_label.config(text=f"LED State: {'ON' if self.led_state else 'OFF'}")
      self.led_label.config(bg='green' if self.led_state else 'red')
      self.toggle_button.config(text=f"Turn {'OFF' if self.led_state else 'ON'}")
      self.toggle_button.config(bg='red' if self.led_state else 'green')

  def on_led_brightness(self, client, userdata, message):
      brightness_value = int(message.payload.decode())
      print(f"Received LED brightness for {self.sensor_id}: {brightness_value}")
      self.cBrightness = brightness_value
      self.brightness_label.config(text=f"Brightness Value: {brightness_value}")

  def disable_all_controls(self):
      self.set_button.config(state=tk.DISABLED)
      self.toggle_button.config(state=tk.DISABLED)
      self.led_value_slider.config(state=tk.DISABLED)

  def enable_all_controls(self):
      self.client.subscribe(self.topic_led_state)
      self.set_button.config(state=tk.NORMAL)
      self.toggle_button.config(state=tk.NORMAL)
      self.led_value_slider.config(state=tk.NORMAL)

  def enable_all_controls_after_delay(self):
      time.sleep(30)
      self.controls_enabled = True
      self.frame.after(0, self.enable_all_controls)
      self.led_value_slider.set(self.cBrightness)

  def set_led_value(self):
      led_value = self.led_value_slider.get()
      self.client.publish(self.topic_led_value_command, led_value)
      print(f"Published LED Value for {self.sensor_id}: {led_value}")
      self.disable_all_controls()
      self.controls_enabled = False
      threading.Thread(target=self.enable_all_controls_after_delay, daemon=True).start()

  def toggle_led(self):
      self.client.unsubscribe(self.topic_led_state)
      self.disable_all_controls()
      self.controls_enabled = False
      self.led_state = not self.led_state
      new_state = 1 if self.led_state else 0
      if not new_state:
          self.led_value_slider.set(0)

      self.led_label.config(text=f"LED State: {'ON' if self.led_state else 'OFF'}")
      self.led_label.config(bg='green' if self.led_state else 'red')
      self.toggle_button.config(bg='red' if self.led_state else 'green')
      self.toggle_button.config(text=f"Turn {'OFF' if self.led_state else 'ON'}")
      self.client.publish(self.topic_led_command, new_state)
      threading.Thread(target=self.enable_all_controls_after_delay, daemon=True).start()


def main():
  root = tk.Tk()
  root.title("MQTT Sensor Data Multiple")
  root.geometry("800x600")  # Set window size

  client = mqtt.Client()

  # Connection status variable
  client.connected_flag = False

  gui_list = []

  def on_message(client, userdata, message):
      """Global message handler for debugging"""
      topic = message.topic
      payload = message.payload.decode()
      print(f"Received message on topic '{topic}': {payload}")

  def on_connect(client, userdata, flags, rc):
      if rc == 0:
          print("Connected with result code 0")
          client.connected_flag = True
          # When reconnected successfully, resubscribe to all GUI topics
          for gui in gui_list:
              gui.subscribe_to_topics()
      else:
          print(f"Failed to connect, return code {rc}")
          client.connected_flag = False

  def on_disconnect(client, userdata, rc):
      print("Disconnected from MQTT with rc =", rc)
      client.connected_flag = False
      # Start reconnection thread
      threading.Thread(target=try_reconnect, daemon=True).start()

  def try_reconnect():
      while not client.connected_flag:
          try:
              print("Trying to reconnect to MQTT broker...")
              client.reconnect()
              time.sleep(1)  # Wait a bit for stability
          except Exception as e:
              print(f"Reconnect failed: {e}")
              time.sleep(5)  # Wait 5 seconds before retry

  # Set up MQTT callbacks
  client.on_connect = on_connect
  client.on_disconnect = on_disconnect
  client.on_message = on_message  # Global message handler for debugging
  
  try:
      client.connect(broker, port)
      client.loop_start()
  except Exception as e:
      print(f"Failed to connect to MQTT broker initially: {e}")
      threading.Thread(target=try_reconnect, daemon=True).start()

  # Create main frame containing everything
  main_frame = tk.Frame(root)
  main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

  # Create canvas and scrollbar
  canvas = tk.Canvas(main_frame)
  scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
  scrollable_frame = tk.Frame(canvas)

  # Configure scrollbar
  scrollable_frame.bind(
      "<Configure>",
      lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
  )

  canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
  canvas.configure(yscrollcommand=scrollbar.set)

  # Pack canvas and scrollbar
  canvas.pack(side="left", fill="both", expand=True)
  scrollbar.pack(side="right", fill="y")

  # Container for sensor GUIs (now using scrollable_frame)
  container = scrollable_frame

  # Add button frame at the top
  button_frame = tk.Frame(root)
  button_frame.pack(pady=10)
  
  def add_gui():
      # Ask user to input sensor ID
      sensor_id = simpledialog.askstring("Input", "Enter Sensor ID:", parent=root)
      if sensor_id is None or sensor_id.strip() == "":
          return
      sensor_id = sensor_id.strip()
      # Check for duplicate ID
      for gui in gui_list:
          if gui.sensor_id == sensor_id:
              messagebox.showerror("Error", f"Sensor ID '{sensor_id}' already exists!")
              return
      
      gui = SensorGUI(container, client, sensor_id)
      gui_list.append(gui)
      
      # Set up message callbacks for this specific GUI
      client.message_callback_add(gui.topic_sensor_data, gui.on_sensor_data)
      client.message_callback_add(gui.topic_led_state, gui.on_led_state)
      client.message_callback_add(gui.topic_led_brightness, gui.on_led_brightness)
      client.message_callback_add(gui.topic_light_sensor, gui.on_sensor_status)
      client.message_callback_add(gui.topic_motion_sensor, gui.on_motion_sensor_status)
        
      # Update scroll region after adding new GUI
      root.after(100, lambda: canvas.configure(scrollregion=canvas.bbox("all")))

  add_button = tk.Button(button_frame, text="ADD", command=add_gui)
  add_button.pack(pady=5)

  # Test button to publish test messages
  def publish_test_message():
      if gui_list:
          test_sensor_id = gui_list[0].sensor_id
          client.publish(f"task11.1/sensorData/{test_sensor_id}", "123.45")
          client.publish(f"task11.1/ledStateData/{test_sensor_id}", "1")
          client.publish(f"task11.1/ledBrightnessData/{test_sensor_id}", "75")
          client.publish(f"task11.1/sensorStatus/{test_sensor_id}", "OK")
          client.publish(f"task11.1/motionSensorStatus/{test_sensor_id}", "OK")
          print(f"Published test messages for sensor {test_sensor_id}")

  test_button = tk.Button(button_frame, text="Test Publish", command=publish_test_message)
  test_button.pack(pady=5)

  # Create first default sensor GUI (can be removed if desired)
  add_gui()

  # Bind mouse wheel for scrolling
  def _on_mousewheel(event):
      canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
  def _bind_to_mousewheel(event):
      canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
  def _unbind_from_mousewheel(event):
      canvas.unbind_all("<MouseWheel>")
    
  canvas.bind('<Enter>', _bind_to_mousewheel)
  canvas.bind('<Leave>', _unbind_from_mousewheel)

  # Internet connection check function (keep as is)
  def check_internet_connection():
      try:
          response = requests.get("http://www.google.com", timeout=5)
          if response.status_code == 200:
              for gui in gui_list:
                  if gui.controls_enabled:
                      gui.enable_all_controls()
          else:
              for gui in gui_list:
                  gui.disable_all_controls()
      except (requests.ConnectionError, requests.Timeout):
          for gui in gui_list:
              gui.disable_all_controls()
      root.after(5000, check_internet_connection)

  check_internet_connection()

  try:
      root.mainloop()
  except KeyboardInterrupt:
      print("Exiting gracefully...")
      client.disconnect()
      sys.exit(0)


if __name__ == "__main__":
  main()
