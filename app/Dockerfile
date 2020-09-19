FROM python:3

ENV PYTHONUNBUFFERED 1

RUN mkdir /app

WORKDIR /app

RUN pip install pipenv

COPY Pipfile* ./

RUN pipenv lock --requirements -d > requirements.txt
RUN pip install -r requirements.txt

COPY . /app/
