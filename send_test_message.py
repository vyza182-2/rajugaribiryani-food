import requests

url = "https://api.deepseek.com/v1/endpoint"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}
data = {
    "your": "request body"
}

response = requests.post(url, headers=headers, json=data)

print(response.status_code)
print(response.json())
