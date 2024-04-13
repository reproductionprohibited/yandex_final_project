FROM python:3.11.4

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

CMD ["sh", "-c", "cd bot && exec python3 bot.py"]
