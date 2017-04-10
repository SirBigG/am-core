 FROM python:3.6

 ENV PYTHONUNBUFFERED 1

 RUN mkdir /am-core
 WORKDIR /am-core
 ADD requirements.txt /am-core/

 RUN pip3 install -r requirements.txt
 RUN pip3 install uwsgi

 RUN mkdir /am-core/tmp
 RUN mkdir /am-core/docker
 ADD docker/uwsgi.ini /am-core/docker/

 ADD . /am-core/
