from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


@dataclass
class WaitTimePrediction:
    consultation_minutes: float
    waiting_minutes: float
    notification_lead_minutes: int


class SmartOPDPredictor:
    def __init__(self) -> None:
        self.pipeline = None

    def train(self, csv_path: str | Path) -> None:
        data = pd.read_csv(csv_path)
        feature_columns = [
            "doctor_id",
            "department",
            "priority",
            "age_band",
            "queue_length",
            "doctor_delay_minutes",
            "slot_hour",
        ]
        features = data[feature_columns]
        target = data["actual_consultation_minutes"]

        preprocessor = ColumnTransformer(
            transformers=[
                (
                    "categorical",
                    OneHotEncoder(handle_unknown="ignore"),
                    ["doctor_id", "department", "priority", "age_band"],
                )
            ],
            remainder="passthrough",
        )

        self.pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("model", RandomForestRegressor(n_estimators=120, random_state=42)),
            ]
        )
        self.pipeline.fit(features, target)

    def predict(self, payload: dict) -> WaitTimePrediction:
        if self.pipeline is None:
            raise RuntimeError("Model must be trained before prediction.")

        frame = pd.DataFrame([payload])
        consultation_minutes = float(self.pipeline.predict(frame)[0])
        waiting_minutes = max(
            0.0,
            (payload["queue_length"] * consultation_minutes) + payload["doctor_delay_minutes"],
        )

        if waiting_minutes >= 45:
            lead = 30
        elif waiting_minutes >= 25:
            lead = 25
        else:
            lead = 20

        return WaitTimePrediction(
            consultation_minutes=round(consultation_minutes, 2),
            waiting_minutes=round(waiting_minutes, 2),
            notification_lead_minutes=lead,
        )


if __name__ == "__main__":
    predictor = SmartOPDPredictor()
    predictor.train(Path(__file__).with_name("training_sample.csv"))
    result = predictor.predict(
        {
            "doctor_id": "DOC-001",
            "department": "General OPD",
            "priority": "elderly",
            "age_band": "60_plus",
            "queue_length": 4,
            "doctor_delay_minutes": 10,
            "slot_hour": 11,
        }
    )
    print(result)
