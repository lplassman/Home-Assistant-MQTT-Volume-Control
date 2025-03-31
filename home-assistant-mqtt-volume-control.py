#!/usr/bin/python3
import time
import paho.mqtt.client as mqtt
import yaml
import alsaaudio
import signal
import sys
from typing import Dict, Any, Optional

# Configuration
DEFAULT_VOLUME = 80
DEFAULT_PUBLISH_INTERVAL = 5  # seconds
shutdown_flag = False

class VolumeControl:
    def __init__(self, device_id: str, config: Dict[str, Any], mqtt_client: mqtt.Client):
        self.id = device_id
        self.config = config
        self.mqttc = mqtt_client
        mqtt_conf = config['mqtt']
        self.volume_topic = f"{mqtt_conf['prefix']}{mqtt_conf['device_prefix']}/{mqtt_conf['id']}"
        self.publish_interval = mqtt_conf.get('publish_interval', DEFAULT_PUBLISH_INTERVAL)
        self.periodic_publish_enabled = self.publish_interval > 0
        self.last_publish_time = 0
        
        # Initialize volume
        self.volume = self.volume_get()
        if 'default_volume' in config['devices'][device_id]:
            self.volume_set(config['devices'][device_id]['default_volume'])

    def publish_current_volume(self) -> None:
        if not self.periodic_publish_enabled or shutdown_flag:
            return
            
        current_time = time.time()
        if current_time - self.last_publish_time >= self.publish_interval:
            current_volume = self.volume_get()
            self._mqtt_publish(f"{self.volume_topic}/state", current_volume)
            self.last_publish_time = current_time
    
    def volume_get(self) -> int:
        card_number = self.config['devices'][self.id]['alsa_number']
        control_name = self.config['devices'][self.id].get('control_name', 'Master')
        
        try:
            mixer = alsaaudio.Mixer(control_name, 0, card_number)
            return int(mixer.getvolume()[0])
        except alsaaudio.ALSAAudioError:
            print(f"Failed to get volume for {control_name}, trying Master...")
            mixer = alsaaudio.Mixer('Master', 0, card_number)
            return int(mixer.getvolume()[0])
    
    def volume_set(self, volume: int) -> None:
        self.volume = volume
        card_number = self.config['devices'][self.id]['alsa_number']
        control_name = self.config['devices'][self.id].get('control_name', 'Master')
        
        try:
            mixer = alsaaudio.Mixer(control_name, 0, card_number)
            mixer.setvolume(volume)
        except alsaaudio.ALSAAudioError:
            mixer = alsaaudio.Mixer('Master', 0, card_number)
            mixer.setvolume(volume)
            
        self._mqtt_publish(f"{self.volume_topic}/state", volume)
        self.last_publish_time = time.time()

    def _mqtt_publish(self, topic: str, payload, retain: bool = True) -> None:
        """Wrapper for MQTT publish with version compatibility"""
        if hasattr(self.mqttc, 'publish') and callable(self.mqttc.publish):
            self.mqttc.publish(topic, payload, retain=retain)

    def volume_up(self) -> None:
        self.volume_set(min(self.volume + 1, 100))

    def volume_down(self) -> None:
        self.volume_set(max(self.volume - 1, 1))

def signal_handler(sig, frame):
    global shutdown_flag
    print("\nReceived shutdown signal, cleaning up...")
    shutdown_flag = True

def load_config() -> Dict[str, Any]:
    try:
        with open('configuration.yaml', 'r') as config_file:
            return yaml.safe_load(config_file)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

def on_connect_v3(client: mqtt.Client, userdata, flags, rc):
    """MQTT v3.1.1 connection callback"""
    if rc != 0:
        print(f"Failed to connect: {mqtt.connack_string(rc)}")
        return
        
    print(f"Connected to MQTT with result code {rc} ({mqtt.connack_string(rc)})")
    _post_connect_setup(client, userdata)

def on_connect_v5(client: mqtt.Client, userdata, flags, reason_code, properties):
    """MQTT v5.0 connection callback"""
    if reason_code.is_failure:
        print(f"Failed to connect: {reason_code}")
        return
        
    print(f"Connected to MQTT with result code {reason_code}")
    _post_connect_setup(client, userdata)

def _post_connect_setup(client: mqtt.Client, userdata):
    """Common post-connection setup for both MQTT versions"""
    config = userdata['config']
    mqtt_conf = config['mqtt']
    
    # Subscribe to control topic
    topic = f"{mqtt_conf['prefix']}{mqtt_conf['device_prefix']}/{mqtt_conf['id']}/set"
    client.subscribe(topic)
    
    # Home Assistant discovery
    discovery_topic = f"{mqtt_conf['discover']}/number/{mqtt_conf['device_prefix']}/{mqtt_conf['id']}/config"
    discovery_payload = {
        "name": f"{mqtt_conf['friendly_name']} Volume",
        "uniq_id": f"{mqtt_conf['id']}1",
        "device": {
            "name": mqtt_conf['device_name'],
            "ids": mqtt_conf['id'],
            "mf": mqtt_conf['device_manufacturer'],
            "mdl": mqtt_conf['device_model'],
            "sw": mqtt_conf['device_sw_version']
        },
        "avty_t": f"{mqtt_conf['prefix']}{mqtt_conf['device_prefix']}/{mqtt_conf['id']}/availability",
        "cmd_t": f"{mqtt_conf['prefix']}{mqtt_conf['device_prefix']}/{mqtt_conf['id']}/set",
        "stat_t": f"{mqtt_conf['prefix']}{mqtt_conf['device_prefix']}/{mqtt_conf['id']}/state",
        "icon": "mdi:volume-high",
        "ret": True
    }
    client.publish(discovery_topic, str(discovery_payload), retain=True)
    client.publish(f"{mqtt_conf['prefix']}{mqtt_conf['device_prefix']}/{mqtt_conf['id']}/availability", "online", retain=True)

def on_message(client, userdata, message):
    try:
        payload = message.payload.decode("utf-8")
        print(f"Received message on {message.topic}: {payload}")
        
        for device in userdata['devices'].values():
            if message.topic == f"{device.volume_topic}/set":
                if payload == 'UP':
                    device.volume_up()
                elif payload == 'DOWN':
                    device.volume_down()
                else:
                    volume = int(payload)
                    if 0 <= volume <= 100:
                        device.volume_set(volume)
    except Exception as e:
        print(f"Error processing message: {e}")

def create_mqtt_client(config: Dict[str, Any], use_mqttv5: bool = False) -> mqtt.Client:
    """Create and configure MQTT client with version detection"""
    mqtt_conf = config['mqtt']
    
    if use_mqttv5:
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=mqtt_conf['id'],
            protocol=mqtt.MQTTv5
        )
        client.on_connect = on_connect_v5
    else:
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION1,
            client_id=mqtt_conf['id'],
            protocol=mqtt.MQTTv311
        )
        client.on_connect = on_connect_v3
    
    client.username_pw_set(mqtt_conf['user'], mqtt_conf['password'])
    return client

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    config = load_config()
    mqtt_conf = config['mqtt']
    
    # Try MQTT v5 first, fall back to v3 if not available
    try:
        client = create_mqtt_client(config, use_mqttv5=True)
    except AttributeError:
        print("MQTT v5 not available, falling back to MQTT v3.1.1")
        client = create_mqtt_client(config, use_mqttv5=False)
    
    # Setup devices
    devices = {
        dev_id: VolumeControl(dev_id, config, client)
        for dev_id, dev_config in config['devices'].items()
        if dev_config['platform'] == 'alsa'
    }
    
    client.user_data_set({'config': config, 'devices': devices})
    client.on_message = on_message
    
    # Set last will
    client.will_set(
        f"{mqtt_conf['prefix']}{mqtt_conf['device_prefix']}/{mqtt_conf['id']}/availability",
        "offline",
        retain=True
    )
    
    try:
        client.connect(mqtt_conf['host'], mqtt_conf['port'])
        client.loop_start()
        
        print("Service started. Waiting for messages...")
        while not shutdown_flag:
            for device in devices.values():
                device.publish_current_volume()
            time.sleep(1)
            
    except Exception as e:
        print(f"Error in main loop: {e}")
    finally:
        print("Shutting down...")
        client.publish(
            f"{mqtt_conf['prefix']}{mqtt_conf['device_prefix']}/{mqtt_conf['id']}/availability",
            "offline",
            retain=True
        )
        client.loop_stop()
        client.disconnect()
        print("Cleanup complete")

if __name__ == "__main__":
    main()