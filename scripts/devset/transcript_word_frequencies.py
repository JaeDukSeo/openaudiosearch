#!/usr/bin/env python
""" transcript_word_frequencies

Word frequencies in transcripts of Devset.

Author(s): datadonk23
Date: 11.11.21
"""

import glob
import collections
import nltk
from nltk.corpus import stopwords
from nltk.stem.snowball import GermanStemmer


def get_txt(transcript_fpath: str):
    """
    Read in transcript.

    :param transcript_fpath: Filepath of transcript
    :return: Text string of transcript
    """

    with open(transcript_fpath, "r") as file:
        return file.read()


def clean_txt(transcript_text: str):
    """

    :param transcript_text: Raw transcript text
    :return: Cleaned transcript text
    """

    cleaned_tokens = []
    stop_words = set(stopwords.words("german"))

    for word in transcript_text.split():
        stem_token = GermanStemmer().stem(word)
        if stem_token not in stop_words:
            cleaned_tokens.append(stem_token)

    return " ".join(cleaned_tokens)


def word_frequencies(transcript_text: str, counter: collections.Counter):
    """
    Calculates word frequencies in given transcript.

    :param transcript_text: Text string of transcript
    :param counter: Counter instance
    :return: Word frequencies
    :return type: collections.Counter
    """

    counter.clear()
    counter.update(clean_txt(transcript_text).split())

    return counter.most_common()


def top_n_words(word_frequencies: list, n: int):
    """
    Top n words and occurrence in word frequency list.

    :param word_frequencies: List of (word, occurrence) tuples
    :return: top n (word, occurrence) tuples
    :return type: list
    """

    return word_frequencies[:n]


if __name__ == '__main__':
    """ Prints Top-n words in Devset transcripts. """
    TOP_N = 15
    SOURCES_DIR = "../../examples/Devset"
    transcript_fpaths = [fpath for fpath in glob.glob(SOURCES_DIR +
                                                      "/*_transcript.txt")]

    for transcript_fpath in transcript_fpaths:
        id = transcript_fpath.split("/")[-1].split("_")[0]
        counter = collections.Counter()
        text = get_txt(transcript_fpath)
        word_frequency_list = word_frequencies(text, counter)
        print(f"Transcript {id}:\n{top_n_words(word_frequency_list, TOP_N)}\n")
