#!/usr/bin/env python
""" evaluate_devset

Evaluate OAS Devset:
  * Keywords
  * Transcripts (TBD)

Author(s): flipsimon, datadonk23
Date: 10.01.22
"""

import httpx
import argparse
import pandas as pd
import time
from datetime import datetime
from string import punctuation

from app.jobs.spacy_pipe import spacy_load
from devset.evaluate_devset_utils import (
    precision_recall_f1, mean_average_precision_k, log_results
)


OAS_URL = 'http://admin:password@localhost:8080/api/v1'
nlp = spacy_load("de_core_news_lg")


def get_true_labels(fpath: str):
    """
    Gets ground truth labels from devset spreadsheet and lowercases them. It
    returns labels as a dict with track ID as key and keywords list as values.

    :param fpath: Filepath to devset spreadsheet
    :return: List of Dicts {cba ID: keywords list}
    :return list: list(dict(cba ID: [keywords]))
    """
    ground_truth = []
    df = pd.read_csv(fpath)
    df["cba_id"] = df["URL"].apply(
        lambda s: "https://cba.fro.at/?p=" + s.split("/")[-1]
    )
    df["keywords"] = df.OAS_tags.str.lower().str.split(",").apply(
        lambda x: [s.strip() for s in x]).tolist()
    for _, row in df.iterrows():
        ground_truth.append({row["cba_id"]: row["keywords"]})

    return ground_truth


def devsetIDs_to_cbaIDs(fpath: str):
    """
    Transforms IDs from devset spreadsheet to CBA IDs in OAS posts
    (identifier field, not post ID!).

    :param fpath: Filepath to devset spreadsheet
    :return: List of OAS identifiers
    """
    df = pd.read_csv(fpath)
    cba_head = "https://cba.fro.at/"
    oas_param = "?p="
    ids = df.URL.apply(lambda s: cba_head + oas_param + s.split("/")[-1])

    return ids.to_list()


def get_post_ids(cba_ids: list):
    """
    Transforms CBA IDs to OAS post IDs.

    :param cba_ids: List of CBA identifiers
    :return: Dict of CBA IDs as keys and OAS post IDs as values
    """
    oas_ids = {}

    for cba_id in cba_ids:
        oas_id = get_oas_id_from_cba_id(cba_id)
        if oas_id is not None:
            oas_ids[cba_id] = oas_id

    return oas_ids


def get_oas_id_from_cba_id(identifier):
    query = {
        "query": {
            "term": {
                "identifier": identifier
            }
        },
        "_source": False,
        "fields": [
            "$meta.id"
        ]
    }
    url = OAS_URL + '/search/oas/_search'
    res = httpx.post(url, json=query).json()
    if not res["hits"]["hits"]:
        return None
    else:
        oas_id = res["hits"]["hits"][0]["_id"]
        return oas_id


def trigger_asr(cba_oas_ids: dict):
    """
    Trigger NLP jobs in OAS on devset posts.
    Blocking, waits till all jobs are completed.

    :param cba_oas_ids:
    :return: Dict of CBA IDs as keys and OAS post IDs as values
    """

    job_ids = []
    print(f"Creating {len(cba_oas_ids)} jobs")
    for cba_id, oas_id in cba_oas_ids.items():
        post = get_post(oas_id)
        for media in post["media"]:
            job_id = create_asr_job(media["$meta"]["id"])
            print(f"created ASR job {job_id}")
        job_ids.append(job_id)

    print(f"Waiting for {len(job_ids)} jobs to complete")
    wait_for_jobs(job_ids)
    print("All jobs finished")

def trigger_nlp(cba_oas_ids: dict):
    """
    Trigger NLP jobs in OAS on devset posts.
    Blocking, waits till all jobs are completed.

    :param cba_oas_ids:
    :return: Dict of CBA IDs as keys and OAS post IDs as values
    """

    job_ids = []
    print(f"Creating {len(cba_oas_ids)} jobs")
    for cba_id, oas_id in cba_oas_ids.items():
        job_id = create_nlp_job(oas_id)
        print(f"created job {job_id} for post {oas_id} (external id {cba_id}")
        job_ids.append(job_id)

    print(f"Waiting for {len(job_ids)} NLP jobs to complete")
    wait_for_jobs(job_ids)
    print("All jobs finished")


def wait_for_jobs(job_ids: list):
    """
    Wait for a list of jobs to be finished.
    As the core currently doesn't have a nice API for this, we poll
    each job until it is finished.
    This blocks until everything is done.
    """
    pending = job_ids
    while pending:
        finished = []
        for job_id in pending:
            if get_job_status(job_id) == "completed":
                finished.append(job_id)

        if len(finished):
            for job_id in finished:
                pending.remove(job_id)
            print(f"Waiting for {len(pending)} of {len(job_ids)} jobs") 

        time.sleep(1)

def create_job(body):
    url = f"{OAS_URL}/job"
    res = httpx.post(url, json=body)
    return str(res.json())


def create_nlp_job(post_id):
    body = {
        "typ": "nlp",
        "subjects": [post_id],
        "args": {"post_id": post_id}
    }
    return create_job(body)


def create_asr_job(media_id):
    body = {
        "typ": "asr",
        "subjects": [media_id],
        "args": {"media_id": media_id}
    }
    return create_job(body)


def get_job_status(job_id):
    job_url = OAS_URL + f"/job/{job_id}"
    res = httpx.get(job_url)
    return res.json()["status"]


def get_post(post_id: str):
    """
    Gets content of post by its ID and returns it as JSON object.

    :param post_id: OAS ID of post
    :return: Post content
    :return type: JSON
    """
    try:
        url = f"{OAS_URL}/post/{post_id}"
        res = httpx.get(url)
        res = res.json()
        return res

    except httpx.RequestError as e:
        print(f"An error occurred while requesting {e.request.url!r}.")


def get_keywords(cba_id_oas_id):
    """
    Gets keywords from devset post.

    :param cba_id_oas_id: (cba_id, oas_id) of post
    :return: Dict of CBA track ID - keywords list
    :return type: dict(cba_id: [keywords])
    """
    cba_id, oas_id = cba_id_oas_id

    post = get_post(oas_id)
    try:
        post_keywords = post["nlp"]["keywords"]
        return {cba_id: post_keywords}
    except Exception as e:
        print(f"Couldn't find keywords for post {post['$meta']['id']}\n{e}")


def get_transcript(cba_id_oas_id):
    """
    Gets transcript from devset post.

    :param cba_id_oas_id: (cba_id, oas_id) of post
    :return: Dict of CBA track ID - transcript
    :return type: dict(cba_id: transcript)
    """
    cba_id, oas_id = cba_id_oas_id

    post = get_post(oas_id)
    try:
        post_transcript = post["media"][0]["transcript"]["text"]
        return {cba_id: post_transcript}
    except Exception as e:
        print(f"Couldn't find transcript for post {post['$meta']['id']}\n{e}")


def flatten_oas_keywords(oas_keywords: list):
    """
    Flattens oas_keywords list to [{cba_ids: [kw]}]. Removes unused
    informations on keyword count and rank.
    Helper for evaluate_keywords().

    :param oas_keywords: List of {cba_id: (kw, count, rank)}
    :return: List of {cba_ids: [kws]}
    """
    oas_plain_keywords = []

    for keyword_dict in oas_keywords:
        cba_id = list(keyword_dict.keys())[0]
        keywords = [keyword_infos[0] for keyword_infos in
                    list(keyword_dict.values())[0]]
        oas_plain_keywords.append({cba_id: keywords})

    return oas_plain_keywords


def clean_keywords(keyword_dicts: list):
    """
    NLP keyword cleansing utility to enhance keyword comparison.
    It does:
        * Lowercasing
        * Punctuation removal
        * String stripping
        * Lemmatize keywords (resp. keyphrases)

    :param keyword_dicts: List of {cba_ids: [kws]}
    :return: cleaned keywords in list of keyword dicts
    """
    cleaned_keyword_dicts = []

    for kw_dict in keyword_dicts:
        for cba_id, kws in kw_dict.items():
            cleaned_kws = []
            for kw in kws:
                cleaned_string = (kw.lower()
                                  .translate(str.maketrans("", "", punctuation))
                                  .strip())
                cleaned_kws.append(" ".join(
                    [token.lemma_ for token in nlp(cleaned_string)]))
            cleaned_keyword_dicts.append({cba_id: cleaned_kws})

    return cleaned_keyword_dicts


def evaluate_keywords(oas_keywords: list, true_keywords: list, metrics: list):
    f"""
    Evaluate OAS keywords against ground truth.
    Current available metrics: Precision, Recall, F1, MAP

    :param oas_keywords: List of {{cba_id: (kw, count, rank)}}
    :param true_keywords: List of {{cba_id: [kws]}}
    :param metrics: List of metrics to compute. available metrics [
    "Precision", "Recall", "F1", "MAP"]
    :return: Evaluation results - dict of metrics as keys and results as values
    :return type: dict
    """
    results = {}
    keywords = flatten_oas_keywords(oas_keywords)

    # Uniform NLP processing of keywords
    keywords = clean_keywords(keywords)
    true_keywords = clean_keywords(true_keywords)

    # Rankless metrics: Precision, Recall, F1
    if any(metric in metrics for metric in ["Precision", "Recall", "F1"]):
        avg_precision, avg_recall, avg_f1 = precision_recall_f1(keywords,
                                                                true_keywords)

        if "Precision" in metrics:
            results["Precision"] = f"{avg_precision:.4f}"
            print(f"Avg Prec: {avg_precision:.4f}")
        if "Recall" in metrics:
            results["Recall"] = f"{avg_recall:.4f}"
            print(f"Avg Rec: {avg_recall:.4f}")
        if "F1" in metrics:
            results["F1"] = f"{avg_f1:.4f}"
            print(f"Avg F1: {avg_f1:.4f}")

    # Rank aware metrics: MAP
    if "MAP" in metrics:
        for k in range(1, 8):
            map_at_k = mean_average_precision_k(keywords, true_keywords, k=k)
            results[f"MAP@k={k}"] = f"{map_at_k:.4f}"
            print(f"MAP@k [k={k}]: {map_at_k:.4f}")

    return results


if __name__ == "__main__":
    """
    Script parses CBA IDs and ground truth keywords (manually labeled)
    from samples in Devset spreadsheet. Transforms CBA IDs to OAS IDs. 
    Triggers NLP job on those samples in OAS. Gets KW extraction results and 
    the corresponding transcript per sample. Evaluates KW extraction results
    (currently Average Precision, Average Recall, Average F1 and MAP@k are 
    supported). Logs evaluation results and OAS responses to 
    oas_worker/devset/evaluations or custom log path.
    """
    parser = argparse.ArgumentParser(description="OAS KW evaluation script")
    parser.add_argument("dataset", nargs="?",
                        default="devset/assets/Devset.csv",
                        type=str, help="Filepath to devset CSV")
    parser.add_argument("log_path", nargs="?",
                        default="devset/evaluations",
                        type=str, help="Path to log evaluation")
    parser.add_argument("--asr", default=False, action='store_true',
                        help="Force run ASR jobs")
    args = parser.parse_args()
    devset_fpath = args.dataset
    log_path = args.log_path
    start = datetime.now()  # track runtime of evaluation

    """ Get true labels """
    true_labels = get_true_labels(devset_fpath)

    """ Get OAS keywords & transcript """
    cba_ids = devsetIDs_to_cbaIDs(devset_fpath)
    oas_post_ids = get_post_ids(cba_ids)

    if args.asr is True:
        trigger_asr(oas_post_ids)

    trigger_nlp(oas_post_ids)
    oas_keywords = [get_keywords(ids) for ids in oas_post_ids.items()]
    oas_transcripts = [get_transcript(ids) for ids in oas_post_ids.items()]

    """ Evaluate """
    keyword_metrics = ["Precision", "Recall", "F1", "MAP"]
    eval_results = evaluate_keywords(oas_keywords, true_labels, keyword_metrics)

    """ LOG Results """
    end = datetime.now()
    eval_duration = str(end - start)
    log_results(eval_results, oas_keywords, true_labels, oas_transcripts,
                log_path, eval_duration)
