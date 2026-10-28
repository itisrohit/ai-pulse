from tests.conftest import login


def test_login_lists_organizations(client):
    _, data = login(client, "ravi@consult.test")
    names = {o["org_name"] for o in data["organizations"]}
    assert names == {"Northwind Logistics", "Bluepeak Retail"}


def test_employee_sees_questions(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    r = client.get("/diagnostic/questions", headers=headers)
    assert r.status_code == 200
    assert any(q["id"] == "sup-drafts" for q in r.json())


def test_admin_dashboard(client):
    headers, data = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = data["organizations"][0]["org_id"]
    r = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    # Support has 5 respondents; Sales, Engineering and HR have fewer and must be hidden
    assert [d["department"] for d in data["departments"]] == ["Support"]
    assert data["hidden_departments"] == ["Sales", "Engineering", "HR"]


def test_admin_cannot_see_other_org(client):
    # Ravi is admin at Bluepeak; he asks for Northwind (id 1) and must still get Bluepeak
    headers, _ = login(client, "ravi@consult.test", "Bluepeak Retail")
    r = client.get("/dashboard?org_id=1", headers=headers)
    assert r.json()["organization"] == "Bluepeak Retail"


def test_select_org_rejects_non_member(client):
    # Priya is only in Northwind (id 1); asking for Bluepeak (id 2) must fail
    _, data = login(client, "priya@northwind.test")
    r = client.post("/auth/select-org", json={"org_id": 2},
                    headers={"Authorization": f"Bearer {data['token']}"})
    assert r.status_code == 403


def test_employee_can_delete_their_answers(client):
    priya, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    admin, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    assert client.get("/dashboard", headers=admin).json()["departments"] != []

    assert client.delete("/reports/me", headers=priya).status_code == 200

    assert client.get("/reports/me", headers=priya).json()["answered"] == 0
    # Support drops to 4 respondents, so it disappears from the dashboard straight away
    assert client.get("/dashboard", headers=admin).json()["departments"] == []
