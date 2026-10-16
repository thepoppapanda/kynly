FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
USER 10001:10001
CMD ["timeout", "30s", "python", "-m", "unittest", "discover", "-s", "tests", "-v"]
