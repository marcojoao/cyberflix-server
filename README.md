# Cyberflix Server Setup Guide

This guide will walk you through setting up and running the Cyberflix Server application using Docker Compose or Procfile.

## Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop) (if using Docker method)
- API keys from:
  - TMDB (The Movie Database)
  - Trakt
  - JustWatch (optional)
  - AniList (optional)

## Setting up Environment Variables

1. **Create Environment File**:
   - Create a file named `.env` in the root directory
   - Use `.env.template` as a reference
   - Fill in the required API keys and configuration

2. **Required Environment Variables**:
   ```plaintext
   TMDB_API_KEY=""        # Your TMDB API key
   TRAKT_CLIENT_ID=""     # Your Trakt client ID
   TRAKT_CLIENT_SECRET="" # Your Trakt client secret
   ```

3. **Optional Environment Variables**:
   ```plaintext
   ANILIST_API_KEY=""     # For anime content
   JUSTWATCH_API_KEY=""   # For streaming availability data
   ```

## Running the Application

### Using Docker (Recommended)

1. **Start the Application**:
   ```bash
   docker-compose up --build
   ```

2. **Access the Application**:
   - Open your browser and navigate to `http://localhost:8000`
   - The API documentation will be available at `http://localhost:8000/docs`

3. **Stop the Application**:
   ```bash
   docker-compose down
   ```

### Using Local Development Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Application**:
   ```bash
   python main.py
   ```

## Development

- API endpoints are available at `/api/v1`
- Swagger documentation is available at `/docs`
- ReDoc documentation is available at `/redoc`

## Troubleshooting

Common issues and solutions:

1. **Docker Connection Issues**:
   - Ensure Docker daemon is running
   - Check if ports are not in use by other applications

2. **API Key Issues**:
   - Verify API keys are correctly formatted
   - Ensure API keys have necessary permissions

## Legal Notice

This software is for educational purposes only. All rights to services like TMDB, Anilist, Justwatch, and others are reserved by their respective owners. Usage of this software must comply with the terms of service of all integrated third-party services.

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
