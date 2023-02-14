FROM python:latest

WORKDIR /app

COPY loadgen.py /app
RUN pip install requests
CMD [ "python", "./loadgen.py"]