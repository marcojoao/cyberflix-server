# Cyberflix Server Setup Guide

This guide will walk you through setting up the environment variables using a `.env` file and running the Cyberflix Server application using Docker Compose or Procfile.

## Setting up Environment Variables

1. **Create a `.env` file**: Start by creating a file named `.env` in the root directory of your Cyberflix Server project.

2. **Add Environment Variables**:
   Add the following environment variables to your `.env` file:

    APP_ENVIRONMENT="PROD"
    TMDB_API_KEY=""
    TRAKT_CLIENT_ID=''
    TRAKT_CLIENT_SECRET=''

 Replace the empty strings with appropriate values. You can obtain TMDB API key, Trakt client ID, and Trakt client secret from their respective developer portals.

## Running with Docker Compose

1. **Ensure Docker is Installed**: Make sure you have Docker installed on your system. If not, download and install it from [here](https://www.docker.com/products/docker-desktop).

2. **Build and Run Containers**:
Open a terminal and navigate to the root directory of your Cyberflix Server project.
Run the following command: `docker-compose up --build`, this command will build the Docker images and start the containers defined in the `docker-compose.yml` file.

3. **Access the Application**:
Once the containers are up and running, you can access Cyberflix Server at `http://localhost:8000` in your web browser.
