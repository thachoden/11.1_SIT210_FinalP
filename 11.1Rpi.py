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

        # Topic riêng theo sensor_id
        self.topic_sensor_data = f"task11.1/sensorData/{sensor_id}"
        self.topic_led_state = f"task11.1/ledStateData/{sensor_id}"
        self.topic_led_brightness = f"task11.1/ledBrightnessData/{sensor_id}"
        self.topic_led_command = f"task11.1/ledStateChangeCommand/{sensor_id}"
        self.topic_led_value_command = f"task11.1/ledValueCommand/{sensor_id}"

        # Frame chứa GUI bộ này
        self.frame = tk.Frame(parent, bd=2, relief=tk.SUNKEN, padx=10, pady=10)
        self.frame.pack(pady=10, fill=tk.X)

        self.title_label = tk.Label(self.frame, text=f"Sensor ID: {sensor_id}", font=("Helvetica", 14, "bold"))
        self.title_label.pack()

        self.lux_label = tk.Label(self.frame, text="Lux Value: N/A", font=("Helvetica", 16))
        self.lux_label.pack(pady=5)

        self.led_label = tk.Label(self.frame, text="LED State: N/A", font=("Helvetica", 16))
        self.led_label.pack(pady=5)

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

        # Đăng ký callback MQTT cho topic của sensor này
        self.client.message_callback_add(self.topic_sensor_data, self.on_sensor_data)
        self.client.message_callback_add(self.topic_led_state, self.on_led_state)
        self.client.message_callback_add(self.topic_led_brightness, self.on_led_brightness)

        # Subscribe các topic này
        self.client.subscribe(self.topic_sensor_data)
        self.client.subscribe(self.topic_led_state)
        self.client.subscribe(self.topic_led_brightness)

    def on_sensor_data(self, client, userdata, message):
        lux_value = message.payload.decode()
        self.lux_label.config(text=f"Lux Value: {lux_value}")

    def on_led_state(self, client, userdata, message):
        self.led_state = message.payload.decode() == "1"
        self.led_label.config(text=f"LED State: {'ON' if self.led_state else 'OFF'}")
        self.led_label.config(bg='green' if self.led_state else 'red')
        self.toggle_button.config(text=f"Turn {'OFF' if self.led_state else 'ON'}")
        self.toggle_button.config(bg='red' if self.led_state else 'green')

    def on_led_brightness(self, client, userdata, message):
        brightness_value = int(message.payload.decode())
        self.cBrightness = brightness_value
        self.brightness_label.config(text=f"Brightness Value: {brightness_value}")

    def disable_all_controls(self):
        self.set_button.config(state=tk.DISABLED)
        self.toggle_button.config(state=tk.DISABLED)
        self.led_value_slider.config(state=tk.DISABLED)

    def enable_all_controls(self):
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

    client = mqtt.Client()

    # Biến trạng thái kết nối
    client.connected_flag = False

    gui_list = []

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected with result code 0")
            client.connected_flag = True
            # Khi kết nối lại thành công, subscribe lại tất cả topic của GUI
            for gui in gui_list:
                client.subscribe(gui.topic_sensor_data)
                client.subscribe(gui.topic_led_state)
                client.subscribe(gui.topic_led_brightness)
        else:
            print(f"Failed to connect, return code {rc}")
            client.connected_flag = False

    def on_disconnect(client, userdata, rc):
        print("Disconnected from MQTT with rc =", rc)
        client.connected_flag = False
        # Bắt đầu thread thử kết nối lại
        threading.Thread(target=try_reconnect, daemon=True).start()

    def try_reconnect():
        while not client.connected_flag:
            try:
                print("Trying to reconnect to MQTT broker...")
                client.reconnect()
                time.sleep(1)  # đợi một chút để ổn định
            except Exception as e:
                print(f"Reconnect failed: {e}")
                time.sleep(5)  # đợi 5 giây rồi thử lại

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    try:
        client.connect(broker, port)
        client.loop_start()
    except Exception as e:
        print(f"Failed to connect to MQTT broker initially: {e}")
        threading.Thread(target=try_reconnect, daemon=True).start()

    container = tk.Frame(root)
    container.pack(pady=10)

    def add_gui():
        # Hỏi người dùng nhập sensor ID
        sensor_id = simpledialog.askstring("Input", "Enter Sensor ID:", parent=root)
        if sensor_id is None or sensor_id.strip() == "":
            return
        sensor_id = sensor_id.strip()
        # Kiểm tra ID có trùng không (nếu muốn)
        for gui in gui_list:
            if gui.sensor_id == sensor_id:
                messagebox.showerror("Error", f"Sensor ID '{sensor_id}' already exists!")
                return
        gui = SensorGUI(container, client, sensor_id)
        gui_list.append(gui)

    add_button = tk.Button(root, text="ADD", command=add_gui)
    add_button.pack(pady=10)

    # Tạo sensor GUI đầu tiên mặc định (có thể bỏ nếu muốn)
    add_gui()

    # Hàm kiểm tra internet (giữ nguyên)
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
