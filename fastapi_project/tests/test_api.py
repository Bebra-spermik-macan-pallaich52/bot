"""Проверки API из задания на настоящей PostgreSQL."""
import pytest
from sqlmodel import Session

PREFIX = "/api/v1"


def request(client, method, path, expected=200, **kwargs):
    response = client.request(method, PREFIX + path, **kwargs)
    assert response.status_code == expected, response.text
    return response.json()


def add_role(client, name="student"):
    return request(client, "POST", "/roles/", 201, json={"name_role": name})["id_role"]


def profile_data(role_id):
    return {"first_name": "Иван", "email": "ivan@example.com",
            "role_id": role_id, "password": "Test-password-1"}


def test_role_crud(client):
    role_id = add_role(client)
    path = f"/roles/{role_id}"
    assert request(client, "GET", path)["name_role"] == "student"
    assert any(row["id_role"] == role_id for row in request(client, "GET", "/roles/"))
    assert request(client, "PUT", path, json={"name_role": "reader"})["name_role"] == "reader"
    request(client, "DELETE", path)
    request(client, "GET", path, 404)
    request(client, "DELETE", path, 404)


def test_role_duplicates(client):
    role_id = add_role(client)
    add_role(client, "admin")
    request(client, "POST", "/roles/", 409, json={"name_role": "student"})
    request(client, "PUT", f"/roles/{role_id}", json={"name_role": "student"})
    request(client, "PUT", f"/roles/{role_id}", 409, json={"name_role": "admin"})
    assert request(client, "GET", f"/roles/{role_id}")["name_role"] == "student"


def test_role_queries(client):
    baseline = request(client, "GET", "/roles/count")
    a = add_role(client, "zz_reader")
    b = add_role(client, "zz_admin")
    assert request(client, "GET", "/roles/count") == baseline + 2
    assert request(client, "GET", "/roles/by-name/zz_reader")["id_role"] == a
    request(client, "GET", "/roles/by-name/zz_missing", 404)
    found = request(client, "GET", "/roles/search?substring=zz_")
    assert {row["id_role"] for row in found} == {a, b}
    ascending = request(client, "GET", "/roles/sorted")
    descending = request(client, "GET", "/roles/sorted?descending=true")
    assert [r["id_role"] for r in ascending] == [r["id_role"] for r in reversed(descending)]
    assert [r["name_role"] for r in ascending if r["id_role"] in {a,b}] == ["zz_admin", "zz_reader"]
    all_rows = request(client, "GET", "/roles/paginated?limit=10000")
    page = request(client, "GET", "/roles/paginated?offset=1&limit=1")
    assert page == all_rows[1:2]


def test_delete_all_roles(client):
    baseline = request(client, "GET", "/roles/count")
    add_role(client)
    add_role(client, "admin")
    assert request(client, "DELETE", "/roles/") == baseline + 2
    assert request(client, "GET", "/roles/") == []
    assert request(client, "DELETE", "/roles/") == 0


@pytest.mark.parametrize("method,path,payload,code", [
    ("POST", "/roles/", {}, 422),
    ("POST", "/roles/", {"name_role": ""}, 422),
    ("POST", "/roles/", {"name_role": "x" * 31}, 422),
    ("GET", "/roles/not-an-id", None, 422),
    ("GET", "/roles/paginated?offset=-1", None, 422),
    ("GET", "/roles/paginated?limit=0", None, 422),
    ("PUT", "/roles/99999999", {"name_role": "missing"}, 404),
    ("POST", "/profiles/", {"email": "x"}, 422),
    ("GET", "/profiles/99999999", None, 404),
    ("DELETE", "/profiles/99999999", None, 404),
])
def test_bad_requests(client, method, path, payload, code):
    result = request(client, method, path, code, **({"json": payload} if payload is not None else {}))
    assert "detail" in result


def test_profile_crud_and_password(api):
    from app.models.profile import Profile
    from app.core.security import verify_password
    client, connection = api
    role_id = add_role(client)
    other_role = add_role(client, "admin")
    data = profile_data(role_id)
    result = request(client, "POST", "/profiles/", 201, json=data)
    profile_id = result["id_users"]
    path = f"/profiles/{profile_id}"
    assert "password" not in result

    def stored_hash():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            return session.get(Profile, profile_id).password

    initial_hash = stored_hash()
    assert initial_hash != data["password"]
    assert verify_password(data["password"], initial_hash)
    assert request(client, "GET", path)["first_name"] == "Иван"
    assert any(p["id_users"] == profile_id for p in request(client, "GET", "/profiles/"))
    assert any(p["id_users"] == profile_id for p in request(client, "GET", f"/profiles/by-role/{role_id}"))
    request(client, "PUT", path, json={**data, "first_name": "Пётр"})
    assert request(client, "GET", path)["first_name"] == "Пётр"
    assert stored_hash() == initial_hash
    updated = {**data, "password": "New-password-2", "role_id": other_role}
    request(client, "PUT", path, json=updated)
    assert stored_hash() != initial_hash and verify_password(updated["password"], stored_hash())
    request(client, "POST", "/profiles/authenticate", 401,
            json={"email": data["email"], "password": data["password"]})
    request(client, "POST", "/profiles/authenticate",
            json={"email": data["email"], "password": updated["password"]})
    assert request(client, "GET", f"/profiles/by-role/{role_id}") == []
    assert request(client, "GET", path)["role_id"] == other_role
    request(client, "DELETE", path)
    request(client, "GET", path, 404)
    request(client, "PUT", path, 404, json=data)


@pytest.mark.parametrize("email,password,code", [
    ("ivan@example.com", "Test-password-1", 200),
    ("ivan@example.com", "wrong", 401),
    ("missing@example.com", "Test-password-1", 401),
])
def test_authentication(client, email, password, code):
    request(client, "POST", "/profiles/", 201, json=profile_data(add_role(client)))
    result = request(client, "POST", "/profiles/authenticate", code,
                     json={"email": email, "password": password})
    if code == 200:
        assert result["email"] == email and "password" not in result


def test_profile_duplicates_and_foreign_keys(client):
    role_id = add_role(client)
    data = profile_data(role_id)
    request(client, "POST", "/profiles/", 201, json=data)
    request(client, "POST", "/profiles/", 409, json=data)
    second = request(client, "POST", "/profiles/", 201, json={**data,"email":"second@example.com"})
    request(client, "PUT", f'/profiles/{second["id_users"]}', 409, json=data)
    request(client, "POST", "/profiles/", 400, json={**data,"email":"bad@example.com","role_id":99999999})
    request(client, "DELETE", f"/roles/{role_id}", 400)
    request(client, "DELETE", "/roles/", 400)
    assert request(client, "GET", f"/roles/{role_id}")["name_role"] == "student"


def test_documentation(client):
    for path in ("/docs", "/redoc"):
        assert client.get(PREFIX + path).status_code == 200
    schema = request(client, "GET", "/openapi.json")
    assert schema["info"]["version"] == "1.0.0"
    assert "password" not in schema["components"]["schemas"]["ProfileRead"]["properties"]
    assert sum(method in {"get","post","put","delete"} for path in schema["paths"].values() for method in path) == 18
