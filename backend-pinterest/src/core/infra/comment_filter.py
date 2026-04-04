from transformers import pipeline


class CommentFilter:
    def __init__(self):
        self.classifier = pipeline("text-classification", model="unitary/toxic-bert")

    def filter_comment_text(self, text: str) -> bool:
        result = self.classifier(text)[0]
        is_toxic_label = result["label"] in [
            "toxic",
            "severe_toxic",
            "obscene",
            "threat",
            "insult",
            "identity_hate",
        ]
        if is_toxic_label and result["score"] > 0.5:
            return False
        else:
            return True
