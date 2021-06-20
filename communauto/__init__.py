import io
import warnings
from collections import ChainMap
from datetime import datetime
from decimal import Decimal
from enum import Enum
from importlib.resources import read_text
from itertools import chain
from typing import Iterable, List

import pytz
import typer
import httpx
from lark import Lark, Transformer
from pydantic import BaseModel, root_validator
from PyPDF3 import PdfFileReader
from structlog import get_logger
from tabulate import tabulate

warnings.filterwarnings("ignore")
log = get_logger()

grammar = read_text("communauto", "grammar.lark")
parser = Lark(grammar, start="invoice")


class City(int, Enum):
    Montreal: int = 59


class Language(str, Enum):
    english: str = "en"
    french: str = "fr"


class Line(BaseModel):
    days: int
    hours: Decimal
    time_price: Decimal
    km: int
    km_price: Decimal
    total_cost: Decimal
    fare: str
    start_date: datetime
    end_date: datetime

    def __repr__(self):
        return f"Line({self.km}km, {self.total_cost}$)"

    @root_validator
    def check_dates(cls, values):
        if values["start_date"] > values["end_date"]:
            d = values["start_date"]
            values["start_date"] = datetime(
                d.year - 1, d.month, d.day, d.hour, d.minute, tzinfo=d.tzinfo
            )
        return values


class Rate(str, Enum):
    eco_extra = "Économique Extra"
    eco_plus = "Économique Plus"
    eco = "Économique"

    def total_cost(self, nb_invoices: int):
        mapping = {
            Rate.eco_extra: Decimal(nb_invoices * 30),
            Rate.eco_plus: Decimal(nb_invoices * 12.5),
            Rate.eco: Decimal(nb_invoices / 12 * 40),
        }
        return mapping[self]


class Estimate(BaseModel):
    rate: Rate
    total_cost: Decimal

    def __repr__(self):
        return f"Estimate({self.rate.value} {self.total_cost}$)"


def estimate(invoices: List[typer.FileBinaryRead]):
    lines = chain(*(extract_lines(invoice) for invoice in invoices))
    # only estimate the lines in invoice that actually were charged.
    lines = [line for line in lines if line.total_cost > Decimal(0)]

    with httpx.Client() as client:
        estimates = list(chain(*(estimate_trip(client, line) for line in lines)))

    result = {
        Rate.eco_extra: Decimal(0),
        Rate.eco_plus: Decimal(0),
        Rate.eco: Decimal(0),
    }
    for estimate in estimates:
        result[estimate.rate] += estimate.total_cost

    print(
        tabulate([k.value, v + k.total_cost(len(invoices))] for k, v in result.items())
    )


def estimate_trip(client: httpx.Client, line: Line) -> Iterable[Estimate]:
    params = {
        "CityId": City.Montreal.value,
        "StartDate": line.start_date.isoformat(),
        "EndDate": line.end_date.isoformat(),
        "Distance": line.km,
        "AcceptLanguage": "en",
        "ExcludePromotion": "true",
    }
    # API returns an ordered list of estimates. Order from best plans to lower
    res = client.get(
        "https://restapifrontoffice.reservauto.net/api/v2/Billing/TripCostEstimate",
        params=params,
    )
    if res.status_code != 200:
        log.error("API failed", message=res.content)
        raise Exception("API failed", res.content)

    data = res.json()
    # filter out flex estimates
    estimates = list(
        filter(
            lambda e: e["serviceType"] == "StationBased",
            data["tripPackageCostEstimateList"],
        )
    )
    for estimate, rate in zip(estimates[:3], [Rate.eco_extra, Rate.eco_plus, Rate.eco]):
        estimate = Estimate(rate=rate, total_cost=estimate["totalCost"])
        log.debug("estimated", line=line, estimate=estimate)
        yield estimate


def extract_lines(invoice: io.BufferedReader) -> Iterable[Line]:
    year_value = None
    for info in extract_info(invoice):
        try:
            tree = parser.parse(info)
        except Exception:
            log.error("Failed", info=info)
            raise

        transformer = TreeToLines()
        transformer.year_value = year_value
        try:
            lines = transformer.transform(tree)
        except Exception:
            log.error("Failed", info=info, tree=tree)
            raise
        log.debug("extracted", lines=lines)
        yield from lines
        year_value = transformer.year_value


def extract_info(invoice: io.BufferedReader) -> Iterable[str]:
    pdf = PdfFileReader(invoice)
    for index, page in enumerate(pdf.pages):
        text = page.extractText()
        start_index = text.find("Période du")
        stop_index0 = text.find("Total trajets :")
        stop_index1 = text.find("Définition des abréviations")
        stop_index = min(stop_index0, stop_index1) if stop_index1 != -1 else stop_index0
        info = text[max(0, start_index) : stop_index]

        no_info_on_page = (start_index, stop_index) == (-1, -1)
        if no_info_on_page:
            continue

        yield info


class TreeToLines(Transformer):
    def year(self, y):
        (year,) = y
        self.year_value = int(year)
        return y

    def integer(self, i):
        (i,) = i
        return i

    def decimal(self, f):
        if len(f) == 1:
            (f,) = f
            return Decimal(str(f))
        elif len(f) == 2:
            f0, f1 = f
            return Decimal(f"{f0}.{f1}")
        elif len(f) == 3:
            f0, f1, f2 = f
            return Decimal(f"{f0}{f1}.{f2}")
        raise NotImplementedError()

    def date(self, d):
        day, month, hour, minute = d
        return datetime(
            self.year_value,
            int(month),
            int(day),
            int(hour),
            int(minute),
            tzinfo=pytz.timezone("America/Toronto"),
        )

    def start_date(self, s):
        (s,) = s
        return {"start_date": s}

    def end_date(self, s):
        (s,) = s
        return {"end_date": s}

    def price(self, p):
        (p,) = p
        return p

    def fare(self, f):
        return {"fare": " ".join(str(t) for t in f)}

    def line(self, line):
        return Line(**ChainMap(*[item for item in line if isinstance(item, dict)]))

    def invoice(self, v):
        return [line for line in v if isinstance(line, Line)]

    def to_dict(key, casting):
        def factory(self, value):
            (value,) = value
            return {key: casting(value)}

        return factory

    days = to_dict("days", int)
    hours = to_dict("hours", Decimal)
    time_price = to_dict("time_price", Decimal)
    km = to_dict("km", int)
    km_price = to_dict("km_price", Decimal)
    total = to_dict("total_cost", Decimal)


def main():  # pragma no cover
    typer.run(estimate)
