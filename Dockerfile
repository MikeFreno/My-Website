FROM python:3.10-alpine

WORKDIR /My_Website

# copy the requirements file used for dependencies
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --trusted-host pypi.python.org -r requirements.txt

COPY . .

ENTRYPOINT ["python", "main.py"]
