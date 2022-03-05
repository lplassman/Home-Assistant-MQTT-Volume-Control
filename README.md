# Home Assistant MQTT Volume Control
Controls an ALSA device using MQTT and Home Assistant. 

### Download required installation files

Make sure git is installed.

```
sudo apt update -y
sudo apt install git -y
```
```
sudo apt-get install python3-pip python3-yaml libasound2-dev python3-dev alsa-utils -y
sudo pip3 install paho-mqtt pyyaml pyalsaaudio
```
Clone this repository
```
git clone https://github.com/lplassman/Home-Assistant-MQTT-Volume-Control.git
```
Edit the configuration.yaml parameters with server info before running

Run the application
```
sudo python3 home-assistant-mqtt-volume-control.py
```
At this point, an entity should show up in Home Assistant with controls for the configured ALSA device.
