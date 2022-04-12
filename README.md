# Centralized CI

This repository is a companion to the talk given at PyCon DE 2022: "FORGET MONO VS. MULTI-REPO: BUILDING CENTRALIZED GIT WORKFLOWS IN PYTHON"

Create a Github application and add the following environment variables to your environment:
``GH_SECRET``: The secret key from your GitHub App
``GH_APP_ID``: The ID of your GitHub App
``GH_PRIVATE_KEY``: The private key of your GitHub App. It looks like:

To allow inbound traffic:
```
ngrok http -subdomain=<subdomain> 8000
```

Run
-----
Using the following command:
cd src && adev runserver
