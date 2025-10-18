FROM mcr.microsoft.com/playwright/python:v1.51.0-jammy

WORKDIR /var/task

RUN pip install awslambdaric

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY handler.py .

ENTRYPOINT ["/usr/bin/python3", "-m", "awslambdaric"]
CMD ["handler.lambda_handler"]

