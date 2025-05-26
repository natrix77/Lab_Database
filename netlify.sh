#!/bin/bash
echo "Using Python version:"
python --version

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements-netlify.txt

echo "Creating distribution directory..."
mkdir -p ./dist
cp -r ./static ./dist/ || echo "No static directory found"
cp -r ./templates ./dist/
cp _redirects ./dist/

echo "Build completed." 