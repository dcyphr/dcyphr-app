import requests

if __name__ == "__main__":
    API_ENDPOINT = "https://api.smmry.com"
    API_KEY = "7A81ABB922"

    data = {
        "SM_API_KEY":API_KEY,
        "SM_URL":"https://en.wikipedia.org/wiki/Science"
    }
    r = requests.get(url=API_ENDPOINT, params=data)
    print(r.json())