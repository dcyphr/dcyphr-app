import requests
from crossref.restful import Works

def summry(text, api_length):
    API_KEY = "7A81ABB922"
    API_ENDPOINT = "https://api.smmry.com"

    data = {
        "sm_api_input":text
    }
    params = {
        "SM_API_KEY":API_KEY,
        "SM_LENGTH":api_length,
    }
    header_params = {"Expect":"100-continue"}
    r = requests.post(url=API_ENDPOINT, params=params, data=data, headers=header_params)
    return r.json()

def get_apa(doi):
    works = Works()
    output = works.doi(doi)
    if output == None:
        return "Not available"
    authors = output['author']
    length = len(authors)
    citation = ""
    for i in range(length):
        citation = citation + authors[i]['family'] + ", " + authors[i]['given'][0] + "., "
    citation = citation + "({}). ".format(output['published-print']['date-parts'][0][0]) + "{}. ".format(output['title'][0]) + output['publisher'] + ", " + "{0}({1}), {2}. doi: {3}".format(output['volume'], output["issue"], output['page'], doi)
    return citation