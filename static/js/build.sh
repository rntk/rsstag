#!/bin/bash
set -e

echo "Installing dependencies..."
npm install --production=false

echo "Building production bundle..."
npm run build

echo "Build completed successfully!"