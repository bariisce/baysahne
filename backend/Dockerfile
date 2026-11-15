FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production
WORKDIR /srv
# Dependencies first (cached layer), then the application code.
COPY pyproject.toml ./
RUN python -c "import tomllib;d=tomllib.load(open('pyproject.toml','rb'))['project'];open('/tmp/req.txt','w').write('\n'.join(d['dependencies']+d['optional-dependencies']['s3']))" \
 && pip install --no-cache-dir -r /tmp/req.txt
COPY . .
RUN useradd --system --uid 10001 app && mkdir -p /data/media && chown -R app /data /srv
USER app
EXPOSE 8100
# --forwarded-allow-ips must list your reverse proxy so client IPs (rate limits, audit) are correct.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8100 --proxy-headers --forwarded-allow-ips=${FORWARDED_ALLOW_IPS:-127.0.0.1}"]
