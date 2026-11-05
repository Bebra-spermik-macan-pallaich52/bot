import pytest

BASE = "/api/v1"


def add_tarif(api, name="Эконом", salary=300):
    response = api.post(BASE + "/tarifs", json={
        "tarif_name": name, "internet": 50, "count_minutes": 500,
        "count_sms": 100, "salary": salary,
    })
    assert response.status_code == 201, response.text
    return response.json()


def add_client(api, phone="+79001234567", tarif=None, **changes):
    data = {
        "number_phone": phone, "id_tarif": tarif, "lastname": "Иванов",
        "firstname": "Иван", "patronymic_name": "Иванович", "date_birthday": "1995-10-20",
        "pasport_serial": "0012", "pasport_number": "000123", "date_issue": "2016-01-01",
    }
    data.update(changes)
    response = api.post(BASE + "/clients", json=data)
    assert response.status_code == 201, response.text
    return response.json()


def test_tarif_crud_and_zero_counts(api):
    assert api.get(BASE + "/tarifs").json() == []
    tarif = add_tarif(api, salary=600.25)
    tarif_id = tarif["id_tarif"]
    assert tarif["salary"] == 600.25
    assert api.get(BASE + "/tarifs").json() == [tarif]
    assert api.get(BASE + "/tarifs/stats/client-count").json() == [{"tarif_name": "Эконом", "client_count": 0}]
    assert api.get(BASE + f"/tarifs/{tarif_id}/client-count").json() == {"tarif_id": tarif_id, "count": 0}
    assert api.get(BASE + "/tarifs/with-client-count").json() == [{**tarif, "client_count": 0}]
    response = api.put(BASE + f"/tarifs/{tarif_id}", json={"salary": "100.10"})
    assert response.status_code == 200
    assert response.json() == {**tarif, "salary": 100.1}
    response = api.delete(BASE + f"/tarifs/{tarif_id}")
    assert response.status_code == 204 and response.content == b""
    assert api.get(BASE + "/tarifs").json() == []


def test_client_crud_and_phone_change(api):
    client = add_client(api)
    phone = client["number_phone"]
    assert client["pasport_serial"] == "0012"
    assert api.get(BASE + "/clients").json() == [client]
    assert api.get(BASE + f"/clients/{phone}").json() == client
    duplicate = api.post(BASE + "/clients", json=client)
    assert duplicate.status_code == 409
    new_phone = "+79990000000"
    response = api.put(BASE + f"/clients/{phone}", json={"lastname": "Петров", "number_phone": new_phone})
    assert response.status_code == 200
    assert response.json() == {**client, "lastname": "Петров", "number_phone": new_phone}
    assert api.get(BASE + f"/clients/{phone}").status_code == 404
    assert api.get(BASE + f"/clients/{new_phone}").status_code == 200
    response = api.delete(BASE + f"/clients/{new_phone}")
    assert response.status_code == 204 and not response.content
    assert api.get(BASE + "/clients").json() == []


def test_search_prefix_sort_and_passport_boundary(api):
    a = add_client(api, date_issue="2015-12-31")
    b = add_client(api, "88001234567", lastname="Петров", date_birthday="1990-05-15", patronymic_name=None)
    assert api.get(BASE + "/clients/search/phone", params={"phone": "+7"}).json() == [{
        "number_phone": a["number_phone"], "lastname": "Иванов", "firstname": "Иван",
    }]
    assert len(api.get(BASE + "/clients/search/phone", params={"phone": "8"}).json()) == 1
    assert api.get(BASE + "/clients/search/phone", params={"phone": "+44"}).json() == []
    assert api.get(BASE + "/clients/sorted-by-birthday").json() == [
        {"full_name": "Петров Иван", "date_birthday": "1990-05-15"},
        {"full_name": "Иванов Иван Иванович", "date_birthday": "1995-10-20"},
    ]
    assert api.get(BASE + "/clients/search/passport-year", params={"year": 2015}).json() == [b]
    assert api.get(BASE + "/clients/search/passport-year", params={"year": 2016}).json() == []
    assert api.get(BASE + "/clients/search/passport-year", params={"year": 9999}).json() == []


def test_joins_cost_counts_and_assignment(api):
    cheap = add_tarif(api, "Эконом", 300)
    expensive = add_tarif(api, "Безлимит", 600)
    unused = add_tarif(api, "Резерв", 1000)
    a = add_client(api, tarif=cheap["id_tarif"])
    b = add_client(api, "+79001234568", expensive["id_tarif"])
    c = add_client(api, "+79001234569")
    all_joined = api.get(BASE + "/clients/with-tarif").json()
    assert all_joined == [{**a, "tarif": cheap}, {**b, "tarif": expensive}, {**c, "tarif": None}]
    assert api.get(BASE + "/clients/search/tarif-cost", params={"minSalary": 300}).json() == [{**b, "tarif": expensive}]
    assert api.get(BASE + "/clients/search/tarif-cost", params={"minSalary": 600}).json() == []
    assert api.get(BASE + f"/tarifs/by-client/{a['number_phone']}").json() == cheap
    assert api.get(BASE + f"/tarifs/by-client/{c['number_phone']}").status_code == 404
    response = api.patch(BASE + "/clients/tarif", params={"phone": c["number_phone"], "id_tarif": cheap["id_tarif"]})
    assert response.status_code == 200 and response.json()["message"]
    assert api.get(BASE + f"/tarifs/by-client/{c['number_phone']}").json() == cheap
    assert api.get(BASE + "/tarifs/stats/client-count").json() == [
        {"tarif_name": "Эконом", "client_count": 2},
        {"tarif_name": "Безлимит", "client_count": 1},
        {"tarif_name": "Резерв", "client_count": 0},
    ]
    assert api.get(BASE + f"/tarifs/{cheap['id_tarif']}/client-count").json()["count"] == 2
    counts = api.get(BASE + "/tarifs/with-client-count").json()
    assert counts == [{**cheap, "client_count": 2}, {**expensive, "client_count": 1}, {**unused, "client_count": 0}]


def test_assigned_tarif_cannot_be_deleted_and_can_be_detached(api):
    tarif = add_tarif(api)
    a = add_client(api, tarif=tarif["id_tarif"])
    path = BASE + f"/tarifs/{tarif['id_tarif']}"
    assert api.delete(path).status_code == 409
    assert len(api.get(BASE + "/tarifs").json()) == 1
    response = api.put(BASE + f"/clients/{a['number_phone']}", json={"id_tarif": None, "patronymic_name": None})
    assert response.status_code == 200 and response.json()["id_tarif"] is None
    assert api.delete(path).status_code == 204
    assert api.get(BASE + f"/clients/{a['number_phone']}").status_code == 200


def test_conflicting_update_preserves_data(api):
    a = add_client(api)
    b = add_client(api, "+79001234568")
    path = BASE + f"/clients/{a['number_phone']}"
    assert api.put(path, json={"number_phone": b["number_phone"]}).status_code == 409
    assert api.put(path, json={"id_tarif": 9999, "lastname": "Изменено"}).status_code == 404
    assert api.get(path).json() == a
    assert api.patch(BASE + "/clients/tarif", params={"phone": a["number_phone"], "id_tarif": 9999}).status_code == 404
    assert api.get(path).json() == a


@pytest.mark.parametrize("method,path,kwargs", [
    ("get", "/clients/+79000000000", {}),
    ("put", "/clients/+79000000000", {"json": {"lastname": "Петров"}}),
    ("delete", "/clients/+79000000000", {}),
    ("patch", "/clients/tarif", {"params": {"phone": "+79000000000", "id_tarif": 1}}),
    ("get", "/tarifs/by-client/+79000000000", {}),
    ("get", "/tarifs/9999/client-count", {}),
    ("put", "/tarifs/9999", {"json": {"salary": 100}}),
    ("delete", "/tarifs/9999", {}),
])
def test_missing_resources(api, method, path, kwargs):
    assert api.request(method, BASE + path, **kwargs).status_code == 404


@pytest.mark.parametrize("path,params", [
    ("/clients/search/phone", {}), ("/clients/search/phone", {"phone": "%"}),
    ("/clients/search/passport-year", {"year": 0}), ("/clients/search/passport-year", {"year": 10000}),
    ("/clients/search/tarif-cost", {"minSalary": -1}), ("/clients/search/tarif-cost", {"minSalary": "NaN"}),
    ("/clients/search/tarif-cost", {}), ("/tarifs/0/client-count", {}),
])
def test_invalid_queries(api, path, params):
    assert api.get(BASE + path, params=params).status_code == 422


@pytest.mark.parametrize("changes", [
    {"salary": -1}, {"salary": "1.001"}, {"count_sms": -1}, {"internet": -1},
    {"tarif_name": "   "}, {"salary": None}, {"unexpected": 1},
])
def test_invalid_tarif_update(api, changes):
    tarif = add_tarif(api)
    assert api.put(BASE + f"/tarifs/{tarif['id_tarif']}", json=changes).status_code == 422
    assert api.get(BASE + "/tarifs").json() == [tarif]


@pytest.mark.parametrize("changes", [
    {"number_phone": "invalid"}, {"number_phone": None}, {"lastname": " "},
    {"date_birthday": "1999-02-30"}, {"date_issue": None}, {"id_tarif": 0}, {"firstname": None},
])
def test_invalid_client_update(api, changes):
    client = add_client(api)
    path = BASE + f"/clients/{client['number_phone']}"
    assert api.put(path, json=changes).status_code == 422
    assert api.get(path).json() == client


def test_create_validation_and_missing_tarif(api):
    assert api.post(BASE + "/tarifs", json={}).status_code == 422
    assert api.post(BASE + "/clients", json={}).status_code == 422
    client = add_client(api)
    client["number_phone"] = "+79000000001"
    client["id_tarif"] = 9999
    assert api.post(BASE + "/clients", json=client).status_code == 404
    client["id_tarif"] = None
    client["number_phone"] = "invalid"
    assert api.post(BASE + "/clients", json=client).status_code == 422
    assert len(api.get(BASE + "/clients").json()) == 1


def test_openapi_docs_and_existing_routes(api):
    assert api.get(BASE + "/docs").status_code == 200
    assert api.get(BASE + "/redoc").status_code == 200
    spec = api.get(BASE + "/openapi.json").json()
    for path in ("/tarifs", "/clients/search/phone", "/clients/tarif", "/clients/with-tarif"):
        assert path in spec["paths"]
    response = api.post(BASE + "/roles/", json={"name_role": "student"})
    assert response.status_code == 201
    assert api.get(BASE + "/roles/").json() == [response.json()]
    response = api.post(BASE + "/profiles/", json={
        "first_name": "Иван", "role_id": response.json()["id_role"],
        "email": "ivan@example.com", "password": "Example-pass-1",
    })
    assert response.status_code == 201
    assert "password" not in response.json()
