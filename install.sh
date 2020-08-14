# init dataset
sqlID = 788767
modelID = 788770
# build Docker images
docker-compose build
# create folders
mkdir ./data
mkdir ./data/sql
mkdir ./data/models
# SQL dump download
wget http://datasets.coronawhy.org/api/access/datafile/$sqlID -O ./data/sql/d64lerqdbpjdga.sql
# Download model
wget http://datasets.coronawhy.org/api/access/datafile/$modelID -O ./data/models/bart.large.cnn.tar.gz