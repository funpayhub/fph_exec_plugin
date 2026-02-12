#!/bin/bash

mkdir -p exec_plugin
cp readme.md manifest.json -t exec_plugin/
cp -r src exec_plugin/
find exec_plugin -name "*__pycache__*" -exec rm -rf {} +
zip -r chat_sync exec_plugin
rm -rf exec_plugin