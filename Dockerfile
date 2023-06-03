FROM python:3.10-bullseye
COPY requirements.txt /app/
WORKDIR /app
RUN apt -y update
RUN apt -y upgrade
RUN apt install -y ffmpeg mediainfo sox libsox-fmt-mp3
RUN pip install -r requirements.txt
COPY . .
CMD ["python3", "run.py"]