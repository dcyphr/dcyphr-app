FROM python:3.6
MAINTAINER Jeffrey Ma
COPY . /dcyphr
WORKDIR /dcyphr
RUN pip install -r requirements.txt
ENTRYPOINT ["python"]
CMD ["application.py"]
