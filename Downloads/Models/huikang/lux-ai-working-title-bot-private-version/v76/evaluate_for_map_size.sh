
MAP_SIZE=$1
for run in {1..200};
    do GFOOTBALL_DATA_DIR=C lux-ai-2021 --seed $run --loglevel 1 --maxtime 10000 \
    --height $MAP_SIZE --width $MAP_SIZE --storeReplay=false --storeLogs=false \
    ./main.py ./ref/main.py >> logs-$MAP_SIZE.txt;
done
