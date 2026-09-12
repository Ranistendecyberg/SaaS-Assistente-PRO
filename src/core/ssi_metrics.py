"""Regras oficiais dos indicadores SSI 2W exibidos pelo MyHonda."""

from __future__ import annotations

import math
import re
import unicodedata

import pandas as pd


SSI_METRICS = {
    "satisfaction": {
        "official": "(%) Satisfação Geral",
        "raw": "Avaliação experiência compra dealer moto",
        "missing_zero": False,
    },
    "recommendation": {
        "official": "(%) Recomendação",
        "raw": "Recomendaria dealer amigo e familia moto",
        "missing_zero": False,
    },
    "installations": {
        "official": "(%) Instalação e Infraestrutura",
        "raw": "Conforto das instalações moto",
        "missing_zero": True,
    },
    "service": {
        "official": "(%) Atendimento",
        "raw": "Atenção no atendimento do vendedor moto",
        "missing_zero": True,
    },
    "test_ride": {
        "official": "(%) Test Ride",
        "raw": "Realizou Test-Ride",
        "missing_zero": False,
    },
    "negotiation": {
        "official": "(%) Negociação",
        "raw": "Negociação Geral",
        "missing_zero": True,
    },
    "delivery": {
        "official": "(%) Avaliação Entrega Motocicleta",
        "raw": "Avaliação Entrega Motocicleta",
        "missing_zero": False,
    },
    "repurchase": {
        "official": "(%) Recompra",
        "raw": "Compraria outra mesmo dealer moto",
        "missing_zero": True,
    },
}


def normalize_label(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join(
        "".join(char for char in text if not unicodedata.combining(char)).lower().split()
    )


def parse_number(value):
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return math.nan
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().replace("%", "")
    if normalize_label(text) in {"", "-", "nan", "none", "<na>", "n/a"}:
        return math.nan
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except (TypeError, ValueError):
        return math.nan


def find_column(df: pd.DataFrame, expected: str):
    target = normalize_label(expected)
    return next((column for column in df.columns if normalize_label(column) == target), None)


def raw_column(df: pd.DataFrame, metric: str):
    spec = SSI_METRICS[metric]
    exact = find_column(df, spec["raw"])
    if exact:
        return exact

    # Compatibilidade com pequenas variações de cabeçalho em bases antigas.
    fragments = {
        "satisfaction": ("experiencia", "compra"),
        "recommendation": ("recomenda", "amigo"),
        "installations": ("conforto", "instala"),
        "service": ("atendimento", "vendedor"),
        "test_ride": ("test", "ride"),
        "negotiation": ("negociacao",),
        "delivery": ("entrega", "motocicleta"),
        "repurchase": ("compraria", "outra"),
    }[metric]
    for column in df.columns:
        label = normalize_label(column)
        if label.startswith("(%)") or "coment" in label:
            continue
        if all(fragment in label for fragment in fragments):
            return column
    return None


def numeric_series(df: pd.DataFrame, column) -> pd.Series:
    if column is None or column not in df.columns:
        return pd.Series(index=df.index, dtype="float64")
    return df[column].apply(parse_number).astype("float64")


def official_series(df: pd.DataFrame, metric: str) -> pd.Series:
    column = find_column(df, SSI_METRICS[metric]["official"])
    return numeric_series(df, column)


def calculate_percentage(df: pd.DataFrame, metric: str) -> float:
    """Agrega a coluna oficial; usa a regra Honda apenas em bases legadas."""
    if df is None or df.empty:
        return 0.0

    official = official_series(df, metric).dropna()
    if len(official) > 0:
        return float(official.mean())

    column = raw_column(df, metric)
    if column is None:
        return 0.0

    if metric == "test_ride":
        answers = df[column].apply(normalize_label)
        valid = answers[answers.isin({"sim", "nao"})]
        return float((valid == "sim").sum() / len(valid) * 100) if len(valid) else 0.0

    scores = numeric_series(df, column)
    scores = scores.where(scores.between(0, 10))
    if SSI_METRICS[metric]["missing_zero"]:
        return float((scores.fillna(0) >= 9).sum() / len(df) * 100)

    valid = scores.dropna()
    return float((valid >= 9).sum() / len(valid) * 100) if len(valid) else 0.0


def recommendation_summary(df: pd.DataFrame) -> dict:
    scores = numeric_series(df, raw_column(df, "recommendation")).dropna()
    scores = scores[scores.between(0, 10)]
    if len(scores) == 0:
        return {"promoters": 0, "neutrals": 0, "detractors": 0, "nps": 0.0, "valid": 0}
    promoters = int((scores >= 9).sum())
    neutrals = int(((scores >= 7) & (scores <= 8)).sum())
    detractors = int((scores <= 6).sum())
    return {
        "promoters": promoters,
        "neutrals": neutrals,
        "detractors": detractors,
        "nps": float((promoters - detractors) / len(scores) * 100),
        "valid": int(len(scores)),
    }


def format_model_year(value) -> str:
    """Converte 2.026/2026.0 para 2026 sem produzir o valor incorreto 226."""
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if normalize_label(text) in {"", "-", "nan", "none", "<na>"}:
        return ""
    digits = re.sub(r"\D", "", text)
    if len(digits) == 4 and digits.startswith(("19", "20")):
        return digits
    number = parse_number(text)
    if not math.isnan(number) and 1900 <= number <= 2200:
        return str(int(number))
    return text
