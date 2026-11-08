"""Dados sintéticos EXCLUSIVOS para testes automatizados. Nunca são carregados pela API."""
from .data import AGES, SEXES, STATES, Row

YEARS = tuple(range(2015, 2025))


def demo_rows():
    for year in YEARS:
        for i, uf in enumerate(STATES):
            for j, age in enumerate(AGES):
                for k, sex in enumerate(SEXES):
                    population = (32000 + i * 16400 + (year - 2015) * 1200) // (j + 1)
                    admissions = population * (180 + j * 220 + k * 33 + (year - 2015) * 7 + (i % 6) * 24) // 100000
                    yield Row(year, uf, age, sex, admissions, population, admissions * (j + 1) // 60,
                              admissions * (4 + j), admissions, admissions * (124300 + j * 35800))
