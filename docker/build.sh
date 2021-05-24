DIR="$(cd "$(dirname "$0")" && pwd)"
cd $DIR/..
docker build -t apluslms/run-radar -f docker/Dockerfile .
