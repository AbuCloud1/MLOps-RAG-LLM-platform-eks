"""
deterministic rag eval, no llm judge so no context window issues
scores recall_at_3 and answer similarity against a written reference

port forward mlflow vllm and qdrant, retrieval app running locally, then run
"""
import os

import mlflow
import requests
from sentence_transformers import SentenceTransformer, util

MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5001")
RETRIEVAL_URL = os.getenv("RETRIEVAL_URL", "http://localhost:8000")
TOP_K = 3

# question, expected source, short reference answer
GOLDEN_SET = [
    ("What sports do I follow?", "02_sports_i_follow.txt",
     "Football including the Premier League and Champions League, boxing and MMA, basketball and the NBA, and cricket."),
    ("What does my gym routine look like?", "01_fitness_and_gym.txt",
     "Weightlifting and strength training focused on compound lifts like squats deadlifts and bench, caring about form and progressive overload, and taking recovery and sleep seriously."),
    ("What do I think about AI and machine learning?", "03_ai_and_ml.txt",
     "Genuinely fascinated by AI and machine learning especially large language models, likes understanding how things work under the hood and learns by building and explaining ideas back."),
    ("What cars am I into?", "04_cars_and_motoring.txt",
     "A car guy who loves petrol engines and car engineering, watches car content on youtube, appreciates German engineering, and likes understanding how cars work mechanically."),
    ("What's my background in tech and devops?", "05_tech_and_devops.txt",
     "Works in cloud and infrastructure, likes kubernetes and terraform, values infrastructure as code and automation, and cares about understanding systems end to end."),
    ("What do I care about when it comes to history and self development?", "06_history_and_self_development.txt",
     "Interested in history and how civilisations rose and fell, and into self development through continuous improvement, reading, and putting ideas into his own words."),
    ("What kind of food and coffee do I like?", "07_food_and_coffee.txt",
     "Enjoys traditional hearty well spiced food made with care, and treats coffee as a daily ritual and a moment to reset."),
    ("Where have I travelled or want to travel?", "08_travel_and_places.txt",
     "Based in Manchester, enjoys travel with history and culture, wants to see more historic cities with strong architecture, and likes trying traditional food while travelling."),
]


def main():
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment("rag-eval-deterministic")

    embedder = SentenceTransformer("all-MiniLM-L6-v2")

    recalls = []
    similarities = []

    for i, (question, expected_source, reference) in enumerate(GOLDEN_SET, start=1):
        search_resp = requests.post(f"{RETRIEVAL_URL}/search", json={"question": question}, timeout=60)
        search_resp.raise_for_status()
        sources = [r["source"] for r in search_resp.json()["results"][:TOP_K]]
        recall = 1.0 if expected_source in sources else 0.0

        ask_resp = requests.post(f"{RETRIEVAL_URL}/ask", json={"question": question}, timeout=60)
        ask_resp.raise_for_status()
        answer = ask_resp.json()["answer"]

        emb = embedder.encode([reference, answer], convert_to_tensor=True)
        similarity = util.cos_sim(emb[0], emb[1]).item()

        recalls.append(recall)
        similarities.append(similarity)

        with mlflow.start_run(run_name=f"lightweight-eval-{i}"):
            mlflow.log_param("question", question)
            mlflow.log_param("expected_source", expected_source)
            mlflow.log_metric("recall_at_3", recall)
            mlflow.log_metric("answer_similarity", similarity)

        print(f"{i}. recall@3={recall} similarity={similarity:.2f} | {question}")

    with mlflow.start_run(run_name="lightweight-eval-summary"):
        mlflow.log_metric("mean_recall_at_3", sum(recalls) / len(recalls))
        mlflow.log_metric("mean_answer_similarity", sum(similarities) / len(similarities))
        mlflow.log_param("num_questions", len(GOLDEN_SET))

    print(f"\nmean recall@3: {sum(recalls) / len(recalls):.2f}")
    print(f"mean answer_similarity: {sum(similarities) / len(similarities):.2f}")


if __name__ == "__main__":
    main()
