#!/bin/sh
NAME=`date -Iseconds`

ts-node src/compare-local.ts --dir logs ${NAME} 2>&1 | tee logs/${NAME}-result.log

