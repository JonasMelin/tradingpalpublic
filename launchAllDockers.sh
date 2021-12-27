
. /home/jonas/.bashrc


echo terminating old containers
docker kill tradingpalavanza
docker kill tradingpalstorage
docker kill mongo
docker kill tradingpal
docker kill tradingpalgui

sleep 2

echo starting new containers
docker run -d --rm -v /media/jonas/USBMAIN1TB/diverse/mongo:/bitnami -p 27018:27017 -e MONGODB_EXTRA_FLAGS='--wiredTigerCacheSizeGB=1' --name mongo bitnami/mongodb:latest
docker run -d --rm --network=host --env TP_PROD=true --name=tradingpalstorage tradingpalstorage
docker run -d --rm --network host --env TP_PROD=true --name tradingpal tradingpal
docker run -d --rm --network host --name tradingpalgui tradingpalgui
docker run -d --rm --network=host --env TP_PROD=true -v /media/jonas/USBMAIN1TB/diverse/ekonomi/passwords:/passwords -v /media/jonas/USBMAIN1TB/diverse/ekonomi/avanzaLogs:/logs --name tradingpalavanza tradingpalavanza:latest
