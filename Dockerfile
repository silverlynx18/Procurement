FROM python:3.10-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    cron build-essential wget unzip --no-install-recommends

# Install Google Chrome and ChromeDriver (Pinning version for stability)
RUN wget -q --show-progress "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/125.0.6422.78/linux64/chromedriver-linux64.zip" -P /tmp/ \
    && unzip /tmp/chromedriver-linux64.zip -d /usr/local/bin/ \
    && rm /tmp/chromedriver-linux64.zip \
    && apt-get update \
    && apt-get install -y google-chrome-stable --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY crontab /etc/cron.d/main-cron
RUN chmod 0644 /etc/cron.d/main-cron && crontab /etc/cron.d/main-cron

COPY ./app /app/app
COPY ./data /app/data
COPY train.py .
COPY model_analyzer.py .

CMD ["cron", "-f"]
