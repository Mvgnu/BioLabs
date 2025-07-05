from Bio import SeqIO
import io

def process_sequence_file(file_content: bytes, fmt: str):
    with io.StringIO(file_content.decode()) as handle:
        records = list(SeqIO.parse(handle, fmt))
    result = []
    for r in records:
        seq_str = str(r.seq)
        length = len(seq_str)
        gc = 0
        if length:
            gc = (seq_str.count("G") + seq_str.count("C")) / length * 100
        result.append({
            "id": r.id,
            "seq": seq_str,
            "length": length,
            "gc_content": gc,
        })
    return result

from Bio import pairwise2
from Bio.Seq import Seq
from Bio.SeqUtils import MeltingTemp as mt
from Bio.Restriction import RestrictionBatch

def align_sequences(seq1: str, seq2: str, mode: str = "global"):
    if mode == "local":
        alignments = pairwise2.align.localms(seq1, seq2, 2, -1, -0.5, -0.1, one_alignment_only=True)
    else:
        alignments = pairwise2.align.globalms(seq1, seq2, 2, -1, -0.5, -0.1, one_alignment_only=True)
    if not alignments:
        return {"aligned_seq1": "", "aligned_seq2": "", "score": 0}
    a = alignments[0]
    return {"aligned_seq1": a.seqA, "aligned_seq2": a.seqB, "score": a.score}


def design_primers(sequence: str, size: int = 20):
    if len(sequence) < size * 2:
        raise ValueError("Sequence too short for primer design")
    fwd = sequence[:size]
    rev = str(Seq(sequence[-size:]).reverse_complement())
    def stats(seq: str):
        length = len(seq)
        gc = 0.0
        if length:
            gc = (seq.count("G") + seq.count("C")) / length * 100
        tm = mt.Tm_Wallace(seq)
        return {"sequence": seq, "gc_content": gc, "tm": tm}
    return {"forward": stats(fwd), "reverse": stats(rev)}


def restriction_map(sequence: str, enzymes: list[str]):
    rb = RestrictionBatch(enzymes)
    sites = rb.search(Seq(sequence))
    # convert sets/lists to sorted lists for JSON serialization
    return {enz.__name__: sorted(pos) for enz, pos in sites.items()}


def parse_genbank_features(file_content: bytes):
    """Parse GenBank file and return basic feature annotations."""
    records = SeqIO.parse(io.StringIO(file_content.decode()), "genbank")
    features = []
    for record in records:
        for f in record.features:
            features.append(
                {
                    "record_id": record.id,
                    "type": f.type,
                    "start": int(f.location.start),
                    "end": int(f.location.end),
                    "strand": f.location.strand,
                    "qualifiers": {k: list(v) for k, v in f.qualifiers.items()},
                }
            )
    return features


def parse_chromatogram(file_content: bytes):
    """Parse ABI/AB1 chromatogram file and return sequence and trace data."""
    record = SeqIO.read(io.BytesIO(file_content), "abi")
    abif = record.annotations.get("abif_raw", {})
    traces = {
        "A": list(abif.get("DATA9", [])),
        "C": list(abif.get("DATA10", [])),
        "G": list(abif.get("DATA11", [])),
        "T": list(abif.get("DATA12", [])),
    }
    return {"sequence": str(record.seq), "traces": traces}


def blast_search(query: str, subject: str):
    """Perform a simple local BLAST-like search using Smith-Waterman."""
    alignments = pairwise2.align.localms(
        query, subject, 2, -1, -0.5, -0.1, one_alignment_only=True
    )
    if not alignments:
        return {"query_aligned": "", "subject_aligned": "", "score": 0, "identity": 0}
    aln = alignments[0]
    matches = sum(
        1 for a, b in zip(aln.seqA, aln.seqB) if a == b and a != "-" and b != "-"
    )
    length = sum(1 for a, b in zip(aln.seqA, aln.seqB) if a != "-" and b != "-")
    identity = (matches / length * 100) if length else 0
    return {
        "query_aligned": aln.seqA,
        "subject_aligned": aln.seqB,
        "score": aln.score,
        "identity": identity,
    }
