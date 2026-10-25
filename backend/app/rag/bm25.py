"""Small dependency-free BM25 (keyword search). Good at exact terms such as 'R grade', '75%', 'ABC'."""
import math
import re
from collections import Counter, defaultdict

STOPWORDS = set("""
a an the and or but if then than so of to in on at by for from with without about into over under between
is are was were be been being am do does did done have has had having can could should would may might must shall will
i me my we our you your he she it its they them their this that these those there here what which who whom whose when where why how
not no nor as also any all each every both either neither some such other another more most less least much many few very
tell please explain give know want need get got let us s t
""".split())

_TOKEN = re.compile(r"[a-z0-9]+")


def stem(w: str) -> str:
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 4 and w.endswith("ed"):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("es") and not w.endswith("ses"):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    return w


def tokenize(text: str):
    return [stem(t) for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS and len(t) > 1]


class BM25:
    def __init__(self, docs, k1=1.5, b=0.5):
        self.k1, self.b = k1, b
        self.doc_tf = [Counter(tokenize(d)) for d in docs]
        self.doc_len = [sum(tf.values()) for tf in self.doc_tf]
        self.avgdl = (sum(self.doc_len) / len(docs)) if docs else 1.0
        self.n = len(docs)
        self.postings = defaultdict(list)
        for i, tf in enumerate(self.doc_tf):
            for term in tf:
                self.postings[term].append(i)

    def idf(self, term):
        df = len(self.postings.get(term, ()))
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def scores(self, query: str):
        scores = defaultdict(float)
        for term in set(tokenize(query)):
            if term not in self.postings:
                continue
            idf = self.idf(term)
            for i in self.postings[term]:
                tf = self.doc_tf[i][term]
                denom = tf + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                scores[i] += idf * tf * (self.k1 + 1) / denom
        return scores
