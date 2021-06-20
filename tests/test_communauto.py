import httpx
import respx
from pytest import fixture


@fixture(
    params=[
        "invoice0",
        "invoice1",
        "invoice2",
        "invoice3",
        "invoice4",
        "invoice_with_2_pages",
    ]
)
def pdf_invoice(request):
    # real invoices not committed as they are not redacted 😬
    with open(f"tests/{request.param}.pdf", "br") as f:
        yield f


def test_extract_lines(pdf_invoice):
    from communauto import extract_lines

    extract_lines(pdf_invoice)


@respx.mock
def test_estimate(pdf_invoice):
    from communauto import estimate

    estimate([pdf_invoice, pdf_invoice])


def test_estimate_trip():
    from communauto import estimate_trip

    estimate_trip


@respx.route(path="/api/v2/Billing/TripCostEstimate")
def estimate_api_response(request):
    return httpx.Response(
        200,
        json={
            "cityId": 59,
            "startDate": "2021-06-22T09:00:00",
            "endDate": "2021-06-22T13:00:00",
            "distance": 50,
            "tripPackageCostEstimateList": [
                {
                    "serviceType": "StationBased",
                    "packageId": 1,
                    "rateId": 141,  # économique extra
                    "durationCost": 19.2,
                    "distanceCost": 2.4,
                    "totalCost": 21.6,
                },
                {
                    "serviceType": "FreeFloating",
                    "packageId": 1,
                    "rateId": 80,  # économique extra flex
                    "durationCost": 9.80,
                    "distanceCost": 12.0,
                    "totalCost": 21.80,
                },
                {
                    "serviceType": "StationBased",
                    "packageId": 2,
                    "rateId": 80,  # économique plus
                    "durationCost": 11.80,
                    "distanceCost": 16.5,
                    "totalCost": 28.30,
                },
                {
                    "serviceType": "FreeFloating",
                    "packageId": 2,
                    "rateId": 80,  # économique plus flex
                    "durationCost": 11.80,
                    "distanceCost": 16.5,
                    "totalCost": 28.30,
                },
                {
                    "serviceType": "StationBased",
                    "packageId": 3,
                    "rateId": 80,  # économique
                    "durationCost": 13.40,
                    "distanceCost": 20.5,
                    "totalCost": 33.90,
                },
                {
                    "serviceType": "FreeFloating",
                    "packageId": 3,
                    "rateId": 80,  # économique flex
                    "durationCost": 13.40,
                    "distanceCost": 20.5,
                    "totalCost": 33.90,
                },
                {
                    "serviceType": "StationBased",
                    "packageId": 4,  # liberté plus
                    "rateId": 80,
                    "durationCost": 25.00,
                    "distanceCost": 8.0,
                    "totalCost": 33.00,
                },
                {
                    "serviceType": "FreeFloating",
                    "packageId": 4,  # liberté plus flex
                    "rateId": 80,
                    "durationCost": 25.00,
                    "distanceCost": 8.0,
                    "totalCost": 33.00,
                },
                {
                    "serviceType": "StationBased",
                    "packageId": 5,
                    "rateId": 80,
                    "durationCost": 21.00,
                    "distanceCost": 8.0,
                    "totalCost": 29.00,
                },
                {
                    "serviceType": "FreeFloating",
                    "packageId": 5,
                    "rateId": 80,
                    "durationCost": 21.00,
                    "distanceCost": 8.0,
                    "totalCost": 29.00,
                },
                {
                    "serviceType": "StationBased",
                    "packageId": 8,  # liberté
                    "rateId": 80,
                    "durationCost": 48.0,
                    "distanceCost": 0.0,
                    "totalCost": 48.0,
                },
                {
                    "serviceType": "FreeFloating",
                    "packageId": 8,
                    "rateId": 219,  # liberté flex
                    "durationCost": 48.00,
                    "distanceCost": 0.0,
                    "totalCost": 48.00,
                },
            ],
        },
    )
