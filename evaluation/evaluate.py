"""
Evaluation: Lightweight RAG quality check.

Production RAG evaluation uses frameworks like Ragas (faithfulness,
answer relevancy, context precision) or an LLM-as-judge. This script
uses keyword matching as a fast, free proxy — good enough to catch
obvious retrieval failures before committing changes to the pipeline.

For each test case we check two things:
  1. Retrieval confidence  — was the similarity score above the threshold?
  2. Keyword hit rate      — does the answer mention expected terms?

A test PASSES when both conditions are met.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.pipeline import RAGPipeline


TEST_CASES = [
    {
        "question": "Why is my Docker container failing to start?",
        "expected_keywords": ["exit code", "docker logs", "entrypoint", "command", "inspect"],
        "min_confidence": 0.30,
        "min_keyword_rate": 0.40,
    },
    {
        "question": "What causes a Kubernetes pod to enter CrashLoopBackOff?",
        "expected_keywords": ["crashloopbackoff", "restart", "logs", "liveness", "exit"],
        "min_confidence": 0.30,
        "min_keyword_rate": 0.40,
    },
    {
        "question": "How do I troubleshoot a failed CI/CD pipeline?",
        "expected_keywords": ["pipeline", "stage", "logs", "artifact", "environment variable"],
        "min_confidence": 0.30,
        "min_keyword_rate": 0.40,
    },
    {
        "question": "How should I investigate high CPU usage on a Linux server?",
        "expected_keywords": ["top", "htop", "process", "cpu", "load average"],
        "min_confidence": 0.30,
        "min_keyword_rate": 0.40,
    },
    {
        "question": "What is a Kubernetes deployment rolling update strategy?",
        "expected_keywords": ["rolling", "rollingupdate", "maxunavailable", "maxsurge", "replicas"],
        "min_confidence": 0.30,
        "min_keyword_rate": 0.40,
    },
    {
        "question": "How do I debug a Docker networking issue?",
        "expected_keywords": ["network", "bridge", "port", "expose", "dns"],
        "min_confidence": 0.30,
        "min_keyword_rate": 0.40,
    },
]


def evaluate(pipeline: RAGPipeline) -> dict:
    results = []
    pass_count = 0
    divider = "=" * 64

    print(f"\n{divider}")
    print("  RAG PIPELINE EVALUATION")
    print(f"  Knowledge base size: {pipeline.document_count()} chunks")
    print(divider)

    for i, tc in enumerate(TEST_CASES, 1):
        result = pipeline.query(tc["question"])
        answer_lower = result["answer"].lower()
        confidence = result["confidence"]

        keywords_found = [kw for kw in tc["expected_keywords"] if kw.lower() in answer_lower]
        keyword_rate = len(keywords_found) / len(tc["expected_keywords"])

        confidence_ok = confidence >= tc["min_confidence"]
        keywords_ok = keyword_rate >= tc["min_keyword_rate"]
        passed = confidence_ok and keywords_ok

        if passed:
            pass_count += 1

        status = "PASS" if passed else "FAIL"
        flags = []
        if not confidence_ok:
            flags.append(f"confidence {confidence:.0%} < {tc['min_confidence']:.0%}")
        if not keywords_ok:
            flags.append(f"keywords {keyword_rate:.0%} < {tc['min_keyword_rate']:.0%}")

        print(f"\n[{i}/{len(TEST_CASES)}] {status}  {':  ' + ', '.join(flags) if flags else ''}")
        print(f"  Q:        {tc['question']}")
        print(f"  Confidence: {confidence:.0%}  |  Keywords: {keywords_found}")
        print(f"  Sources:  {result['sources']}")

        results.append({
            "question": tc["question"],
            "status": status,
            "confidence": confidence,
            "keyword_rate": keyword_rate,
            "keywords_found": keywords_found,
            "sources": result["sources"],
        })

    pass_rate = pass_count / len(TEST_CASES)
    print(f"\n{divider}")
    print(f"  RESULT: {pass_count}/{len(TEST_CASES)} passed  ({pass_rate:.0%})")
    print(divider + "\n")

    return {"results": results, "pass_rate": pass_rate}


if __name__ == "__main__":
    pipeline = RAGPipeline()
    if pipeline.document_count() == 0:
        print(
            "\nKnowledge base is empty.\n"
            "Run the Streamlit app first and ingest the docs/ folder documents.\n"
        )
        sys.exit(1)
    evaluate(pipeline)
