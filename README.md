# Centralized CI

Add the following environment variables.
``GH_SECRET``: The secret key from your GitHub App
``GH_APP_ID``: The ID of your GitHub App
``GH_PRIVATE_KEY``: The private key of your GitHub App. It looks like:

To allow inbound traffic:
```
ngrok http --region=eu --hostname=centralci.eu.ngrok.io 800
```

Run
-----
Using the following command:
adev runserver webservice