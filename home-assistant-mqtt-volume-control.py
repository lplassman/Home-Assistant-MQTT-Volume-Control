#!/usr/bin/python3

import paho.mqtt.client as mqtt
import yaml
import math

import alsaaudio

#sudo apt-get install python3-pip
#sudo pip3 install paho-mqtt
#sudo apt-get install python3-yaml, sudo pip3 install pyyaml
#sudo apt-get install libasound2-dev, sudo apt-get install python3-dev, sudo apt-get install alsa-utils 
#sudo pip3 install pyalsaaudio

# Initial volume for devices that don't override this in their config:
default_volume = 80

# Generic class to control audio volumes
class VolumeControl:

  def __init__(self, device_id):
    self.id = device_id
    self.volume_topic = str(device_mqtt_prefix)+"/number/"+str(device_prefix)+"/"+str(device_mqtt_id)
    
    if default_volume in config['devices'][self.id]:
      self.volume_set(config['devices'][self.id]['default_volume'])
    else:
      print(self.volume_get())
      #self.volume_set(default_volume)

  # def discovery(self):
  def volume_get(self):
    print("Getting Volume from AlsaMixer")
    card_number = config['devices'][self.id]['alsa_number']
    control_name = config['devices'][self.id]['control_name'] #this can be found using "amixer -c <card_number>" - the name will appear after the "Simple mixer control" heading
    try:
        mixer = alsaaudio.Mixer(control_name,0,card_number)
    except Exception:
        mixer = alsaaudio.Mixer('Master',0,card_number)
        pass 
    get_volume = mixer.getvolume()
    get_volume = int(get_volume[0])
    return get_volume    
  
  def volume_set(self,volume):
    self.volume = volume
    card_number = config['devices'][self.id]['alsa_number'] #this is the alsa number
    control_name = config['devices'][self.id]['control_name'] #this can be found using "amixer -c <card_number>" - the name will appear after the "Simple mixer control" heading
    try:
        mixer = alsaaudio.Mixer(control_name,0,card_number)
    except Exception:
        mixer = alsaaudio.Mixer('Master',0,card_number)
        pass 
    print("Setting volume to:",self.volume)    
    mixer.setvolume(self.volume) 
    mqttc.publish(self.volume_topic + '/state', self.volume)

  def volume_up(self):
    volume = self.volume + 1
    if volume > 100:
      volume = 100
    self.volume_set(volume)

  def volume_down(self):
    volume = self.volume - 1
    if volume < 1:
      volume = 1
    self.volume_set(volume)


class AlsaVolumeControl(VolumeControl):
  
  def __init__(self,id):
    super().__init__(id)

def load_config():
  # Read the configuration file
  print("Loading Configuration File...")
  config_file = open('configuration.yaml', 'r')
  # Parse the configuration into a dictionary
  config = yaml.safe_load(config_file)
  config_file.close
  print("Configuration Loaded")
  return config
  
def on_connect (client, userdata, flags, rc):
 print("Connected to MQTT with result code", rc)
 mqttc.subscribe(str(device_mqtt_prefix)+"/number/"+str(device_prefix)+"/"+str(device_mqtt_id)+"/set")
 VolumeConfig = "{\"name\": \""+str(friendly_name)+" Volume\", \"uniq_id\":"+str(device_mqtt_id)+"1, \"device\": {\"name\": \""+str(device_name)+"\", \"ids\":"+str(device_mqtt_id)+", \"mf\": \""+str(device_manufacturer)+"\", \"mdl\": \""+str(device_model)+"\", \"sw\": \""+str(device_sw_version)+"\"},\"avty_t\": \""+str(device_mqtt_prefix)+"/number/"+str(device_prefix)+"/"+str(device_mqtt_id)+"/availability\", \"cmd_t\": \""+str(device_mqtt_prefix)+"/number/"+str(device_prefix)+"/"+str(device_mqtt_id)+"/set\", \"stat_t\": \""+str(device_mqtt_prefix)+"/number/"+str(device_prefix)+"/"+str(device_mqtt_id)+"/state\", \"icon\":\"mdi:volume-high\", \"ret\": \"true\"}"
 mqttc.publish(str(device_mqtt_prefix)+"/number/"+str(device_prefix)+"/"+str(device_mqtt_id)+"/config",VolumeConfig,0,True)
 mqttc.publish(str(device_mqtt_prefix)+"/number/"+str(device_prefix)+"/"+str(device_mqtt_id)+"/availability","online",0,True)
 #mqttc.publish(self.volume_topic, self.volume)

def on_message(client, userdata, message):
  print("received message")    
  payload = str(message.payload.decode("utf-8"))
  topic = message.topic
  print(topic + payload)
  for id, device in devices.items():
    if topic == device.volume_topic + '/set':
      if payload == 'UP':
        device.volume_up()
      elif payload == 'DOWN':
        device.volume_down()
      else:
        volume = int(payload)
        if (volume >= 0 and volume <= 100):
          device.volume_set(volume)

## Main routine ##

# Load the configuration file
config = load_config()

device_mqtt_id = config['mqtt']['id']
device_mqtt_prefix = config['mqtt']['prefix']
friendly_name = config['mqtt']['friendly_name']
device_prefix = config['mqtt']['device_prefix']
device_name = config['mqtt']['device_name']
device_manufacturer = config['mqtt']['device_manufacturer']
device_model = config['mqtt']['device_model']
device_sw_version = config['mqtt']['device_sw_version']


# Initialize the mqtt client
mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, config['mqtt']['id']) # Create a MQTT client object with the given ID in the configuration
mqttc.username_pw_set(config['mqtt']['user'], config['mqtt']['password'])
mqttc.on_connect = on_connect
mqttc.on_message = on_message
mqttc.will_set(str(device_mqtt_prefix)+"/number/"+str(device_prefix)+"/"+str(device_mqtt_id)+"/availability","offline",0,True)
mqttc.connect(config['mqtt']['host'], config['mqtt']['port'])


# Populate the device list
devices = {}
devices_alsa = {}
for device_id, device_config in config['devices'].items():
  if device_config['platform'] == 'alsa':
    devices[device_id] = AlsaVolumeControl(device_id)

# Loop
mqttc.loop_forever()
