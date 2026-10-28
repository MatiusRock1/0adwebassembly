FROM mcr.microsoft.com/playwright/python:v1.56.0-noble@sha256:a7f6cf3ae520c9d670ad956572c13747ed5abdbba5123a01526f873ed1662528
RUN pip install --no-cache-dir playwright==1.56.0 Pillow==11.3.0
COPY scripts/serve-phase2.py scripts/verify-browser.py /opt/
COPY --from=browser / /browser
ENTRYPOINT ["python", "/opt/verify-browser.py"]

