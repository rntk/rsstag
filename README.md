### Build js bundle
`cd static/js`

```docker run -it --rm -v `pwd`/../css:/css -v `pwd`:/app -w /app node:20 ./build.sh```