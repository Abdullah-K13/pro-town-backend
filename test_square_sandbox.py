import requests
import asyncio
import httpx

client_id = "sandbox-sq0idb-Kc14GCqOGMfQK69l0BMwcQ"
client_secret = "sandbox-sq0csb-76-SgaqbzDPb5NBP0uQD8Cg2SJEQKuYdQtW-cxHjMBM"

# The Square API URL to get the OAuth access token
token_url = "https://connect.squareupsandbox.com/oauth2/token"  # Use sandbox URL

# NOTE: You need to get the authorization code from the OAuth flow first
# The authorization_code variable below should be the CODE returned after user authorization,
# NOT the full authorization URL
authorization_code = "YOUR_AUTHORIZATION_CODE_HERE"  # Replace with actual code from OAuth redirect

# Prepare the payload to send in the POST request
payload = {
    "client_id": client_id,
    "client_secret": client_secret,
    "code": authorization_code,
    "grant_type": "authorization_code"
    # Note: redirect_uri is optional for server-side apps
}

# Option 1: Using requests (synchronous, simpler)
def get_oauth_token_sync():
    response = requests.post(token_url, data=payload)
    
    if response.status_code == 200:
        data = response.json()
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        print(f"Access Token: {access_token}")
        print(f"Refresh Token: {refresh_token}")
        return access_token
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

# Option 2: Using httpx (async)
async def get_oauth_token_async():
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=payload)
    
    if response.status_code == 200:
        data = response.json()
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        print(f"Access Token: {access_token}")
        print(f"Refresh Token: {refresh_token}")
        return access_token
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

# Run the function
if __name__ == "__main__":
    # Use synchronous version (simpler)
    access_token = get_oauth_token_sync()
    
    # Or use async version:
    # access_token = asyncio.run(get_oauth_token_async())
    
    if access_token:
        print("\n✅ Success! Add this to your .env file:")
        print(f"SQUARE_ACCESS_TOKEN={access_token}")
