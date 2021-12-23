from app.worker import worker
import httpx
import json

import wikipedia

from qwikidata.entity import WikidataItem, WikidataLexeme, WikidataProperty
from qwikidata.linked_data_interface import get_entity_dict_from_api


@worker.job(name="naive_ned")
def naive_ned(ctx, args):
    """Simple implementation of naive named entity linking with Wikidata.
It simply queries the Wikidata Search API and takes the first result.

    Args:
        ctx (Context): The context object contains the worker ID, the current job and enables access to the core client
        args ({id: string}): post_id

    Returns:
        patches: json patch
    """
    post_id = args["post_id"]

    post = ctx.get(f"/post/{post_id}")
    guid = post["$meta"]["guid"]
    if post["nlp"] is None or post["nlp"]["ner"] is None:
        return {}
    nlp_data = post["nlp"]
    result  =  {}
    wikipedia.set_lang("de")

    for item in nlp_data["ner"]:
        if item[1] == "PER" or item[1] == "LOC":
            print(20 * "#")
            print(item)
            search_res = wikipedia.search("\"" + item[0] + "\"" , results=1)
            if len(search_res) > 0:
                page = wikipedia.page(search_res[0])
                qid = get_qid(page.title, page.pageid)
                print(page.title, qid)

                ent = get_entity_dict_from_api(qid)

                wikiitem = WikidataItem(ent)
                print(wikiitem)
                result[item[0]] = {"description": wikiitem.get_description(), "qid": qid,  }  
    print(result)

    nlp_data["ned"] = result        
    
    patch = [
        {"op": "replace", "path": "/nlp", "value": nlp_data},
    ]
    patches = { guid: patch }

    return {
        "patches": patches
    }

def get_qid(title, id):
    r = httpx.get('https://de.wikipedia.org/w/api.php?action=query&prop=pageprops&ppprop=wikibase_item&redirects=1&titles={}&format=json'.format(title))
    try:
        pprops = json.loads(r.text)
        if pprops['query']['pages'][id]["pageprops"]["wikibase_item"]:
            qid = pprops['query']['pages'][id]["pageprops"]["wikibase_item"]
    except:
        return {}
    return qid

def get_candidates(query):
    r = httpx.get('https://www.wikidata.org/w/api.php?action=wbsearchentities&search={}&language=de&format=json'.format(query))
    print(20 * "#")
    print(r)
    return r.text

# https://www.wikidata.org/w/api.php?action=help&modules=wbgetentities
# https://www.wikidata.org/w/api.php?action=wbgetentities&ids=Q1%7CQ42&props=descriptions&languages=en%7Cde%7Cfr