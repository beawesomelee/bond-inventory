#!/bin/bash

# Add all changes
git add .

# Prompt for commit message
echo "Enter commit message:"
read commit_message

# Commit changes
git commit -m "$commit_message"

# Push to GitHub
git push origin main

# Push to Heroku
git push heroku main