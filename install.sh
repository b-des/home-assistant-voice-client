#!/bin/bash
sudo apt update
sudo apt-get install -y python3-dev build-essential python3-pyaudio portaudio19-dev

python -m venv env
source env/bin/activate

pip install pyaudio
pip install playsound
pip install python-dotenv
pip install pyzmq
pip install netifaces
pip install torch
pip install openwakeword
pip install silero-vad
pip install pysilero-vad


cat > /etc/asound.conf << EOF
defaults.pcm.card 3
defaults.ctl.card 1
EOF


cat > /etc/systemd/system/assistant.service << EOF
[Unit]
Description=Assistant Service
After=multi-user.target

[Service]
Type=idle
Restart=on-failure
User=orangepi
ExecStart=/bin/bash -c 'cd /home/orangepi/assistant/ && source env/bin/activate && python main.py'

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable assistant
sudo systemctl start assistant
sleep 3
sudo systemctl status assistant
sudo systemctl stop assistant