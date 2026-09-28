FROM python:3-alpine

EXPOSE 8000

RUN pip install --no-cache-dir \
    markdown-it-py==4.2.0 \
    mdit-py-plugins==0.6.1 \
    pygments==2.21.0
WORKDIR /app
COPY . build/
RUN python build/docker/build_site.py ./build ./build-out
WORKDIR /app/build-out

CMD [ "python", "-m", "http.server", "8000" ]
