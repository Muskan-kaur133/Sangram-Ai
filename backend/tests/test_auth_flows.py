"""End-to-end auth flows against a real (SQLite) database - Developer 2."""

from sqlalchemy import func, select

from app.db.auth_models import UserSession
from app.proposals.entities import Battle, Profile, SavedAnswer, User

PW = "correct-horse-9"


async def register(client, email="ada@example.com", name="Ada Lovelace", password=PW):
    return await client.post("/api/auth/register", json={"name": name, "email": email, "password": password})


async def test_register_sets_cookies_and_signs_in(client, outbox):
    r = await register(client, email="Ada@Example.com")
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "ada@example.com"  # normalised
    assert body["email_verified"] is False
    set_cookie = " ".join(r.headers.get_list("set-cookie")).lower()
    assert "sangram_session=" in set_cookie and "httponly" in set_cookie
    assert "sangram_refresh=" in set_cookie and "path=/api/auth" in set_cookie
    assert "password" not in r.text.lower()
    assert len(outbox.messages) == 1
    me = await client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["tier"] == "free"
    assert me.json()["is_verified"] is False


async def test_duplicate_email_conflicts_case_insensitively(client):
    assert (await register(client)).status_code == 201
    r = await register(client, email="ADA@example.com")
    assert r.status_code == 409 and r.json()["code"] == "CONFLICT"


async def test_weak_password_rejected(client):
    r = await register(client, password="12345678")
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_ERROR"


async def test_login_wrong_password_and_unknown_email_look_identical(client):
    await register(client)
    bad_pw = await client.post("/api/auth/login", json={"email": "ada@example.com", "password": "nope-nope-1"})
    unknown = await client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "nope-nope-1"})
    assert bad_pw.status_code == unknown.status_code == 401
    assert bad_pw.json()["message"] == unknown.json()["message"]


async def test_login_body_never_contains_refresh_token(client):
    await register(client)
    client.cookies.clear()
    r = await client.post("/api/auth/login", json={"email": "ada@example.com", "password": PW})
    assert r.status_code == 200
    assert r.json()["access_token"] and not r.json().get("refresh_token")


async def test_email_verification_happy_path_and_attempt_limit(client, outbox):
    await register(client)
    for _ in range(5):
        bad = await client.post("/api/auth/verify-email", json={"code": "000000"})
        assert bad.status_code == 422
    # Even the correct code is refused after 5 failures: must request a new one.
    locked = await client.post("/api/auth/verify-email", json={"code": outbox.last_code()})
    assert locked.status_code == 422
    # Resend is rate limited right after registration.
    assert (await client.post("/api/auth/resend-verification")).status_code == 429


async def test_email_verification_succeeds_with_right_code(client, outbox):
    await register(client)
    ok = await client.post("/api/auth/verify-email", json={"code": outbox.last_code()})
    assert ok.status_code == 200 and ok.json()["verified"] is True
    assert (await client.get("/api/auth/me")).json()["is_verified"] is True


async def test_logout_revokes_token_server_side(client):
    await register(client)
    access = client.cookies.get("sangram_session")
    assert (await client.post("/api/auth/logout")).status_code == 200
    # Replaying the old access token must fail even though the JWT itself has not expired.
    replay = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert replay.status_code == 401


async def test_refresh_rotates_and_old_refresh_token_dies(client):
    await register(client)
    old_refresh = client.cookies.get("sangram_refresh")
    assert (await client.post("/api/auth/refresh")).status_code == 200
    new_refresh = client.cookies.get("sangram_refresh")
    assert new_refresh and new_refresh != old_refresh
    client.cookies.clear()
    # The pre-rotation token is dead (replay), the rotated one still works.
    assert (await client.post("/api/auth/refresh", headers={"X-Refresh-Token": old_refresh})).status_code == 401
    assert (await client.post("/api/auth/refresh", headers={"X-Refresh-Token": new_refresh})).status_code == 200


async def test_tampered_and_garbage_tokens_rejected(client):
    for tok in ["garbage", "a.b.c", ""]:
        r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401


async def test_password_reset_flow_revokes_all_sessions(client, client_b, outbox):
    await register(client)
    await client_b.post("/api/auth/login", json={"email": "ada@example.com", "password": PW})
    client.cookies.clear()
    f = await client.post("/api/auth/forgot-password", json={"email": "ada@example.com"})
    assert f.status_code == 200
    token = outbox.last_reset_token()
    r = await client.post("/api/auth/reset-password", json={"token": token, "newPassword": "brand-new-pass-7"})
    assert r.status_code == 200
    # token is single-use
    again = await client.post("/api/auth/reset-password", json={"token": token, "newPassword": "another-pass-88"})
    assert again.status_code == 422
    # all existing sessions died
    assert (await client_b.get("/api/auth/me")).status_code == 401
    # old password no longer works, new one does
    assert (await client.post("/api/auth/login", json={"email": "ada@example.com", "password": PW})).status_code == 401
    ok = await client.post("/api/auth/login", json={"email": "ada@example.com", "password": "brand-new-pass-7"})
    assert ok.status_code == 200


async def test_forgot_password_does_not_reveal_unknown_email(client, outbox):
    r = await client.post("/api/auth/forgot-password", json={"email": "ghost@example.com"})
    assert r.status_code == 200 and outbox.messages == []


async def test_change_password_keeps_current_session_only(client, client_b):
    await register(client)
    await client_b.post("/api/auth/login", json={"email": "ada@example.com", "password": PW})
    wrong = await client.post("/api/auth/change-password", json={"currentPassword": "bad-bad-bad1", "newPassword": "fresh-pass-123"})
    assert wrong.status_code == 422  # not 401, so the UI does not log the user out
    ok = await client.post("/api/auth/change-password", json={"currentPassword": PW, "newPassword": "fresh-pass-123"})
    assert ok.status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 200
    assert (await client_b.get("/api/auth/me")).status_code == 401


async def test_sessions_list_and_revoke_own_session(client, client_b):
    await register(client)
    await client_b.post("/api/auth/login", json={"email": "ada@example.com", "password": PW})
    sessions = (await client.get("/api/auth/sessions")).json()
    assert len(sessions) == 2 and sum(s["is_current"] for s in sessions) == 1
    other = next(s for s in sessions if not s["is_current"])
    assert (await client.delete(f"/api/auth/sessions/{other['id']}")).status_code == 200
    assert (await client_b.get("/api/auth/me")).status_code == 401


# ------------------------------ data isolation ------------------------------

async def test_user_cannot_revoke_another_users_session(client, client_b):
    await register(client, email="a@example.com")
    await register(client_b, email="b@example.com", name="Bob Builder")
    a_session = (await client.get("/api/auth/sessions")).json()[0]["id"]
    r = await client_b.delete(f"/api/auth/sessions/{a_session}")
    assert r.status_code == 404  # not 403: existence is not revealed
    assert (await client.get("/api/auth/me")).status_code == 200  # A is unaffected


async def test_sessions_list_only_shows_own_sessions(client, client_b):
    await register(client, email="a@example.com")
    await register(client_b, email="b@example.com", name="Bob Builder")
    ids_a = {s["id"] for s in (await client.get("/api/auth/sessions")).json()}
    ids_b = {s["id"] for s in (await client_b.get("/api/auth/sessions")).json()}
    assert ids_a and ids_b and ids_a.isdisjoint(ids_b)


async def test_profile_endpoints_only_touch_own_profile(client, client_b):
    await register(client, email="a@example.com", name="Alice A")
    await register(client_b, email="b@example.com", name="Bob B")
    await client.put("/api/users/me/profile", json={"name": "Alice Renamed"})
    assert (await client_b.get("/api/users/me/profile")).json()["name"] == "Bob B"
    assert (await client.get("/api/users/me/profile")).json()["name"] == "Alice Renamed"


async def test_profile_and_preferences_validation(client):
    await register(client)
    assert (await client.put("/api/users/me/profile", json={"avatar": "javascript:alert(1)"})).status_code == 422
    assert (await client.put("/api/users/me/preferences", json={"theme": "neon", "motion": "full"})).status_code == 422
    ok = await client.put("/api/users/me/preferences", json={"theme": "navy", "motion": "reduced"})
    assert ok.status_code == 200 and ok.json()["theme"] == "navy"


async def test_onboarding_persists(client):
    await register(client)
    r = await client.put(
        "/api/users/me/onboarding",
        json={"occupation": "Engineer", "models": ["claude", "chatgpt", "claude"], "archetype": "pragmatist"},
    )
    body = r.json()
    assert r.status_code == 200 and body["onboarding_completed"] is True
    assert body["preferences"]["default_models"] == ["claude", "chatgpt"]


async def test_delete_account_requires_password_and_cascades(client, client_b, db_factory):
    await register(client, email="a@example.com", name="Alice A")
    await register(client_b, email="b@example.com", name="Bob B")
    async with db_factory() as db:
        users = (await db.execute(select(User))).scalars().all()
        a = next(u for u in users if u.email == "a@example.com")
        b = next(u for u in users if u.email == "b@example.com")
        for owner, q in ((a, "A's private question?"), (b, "B's private question?")):
            db.add(Battle(id=f"bt-{owner.email[0]}", user_id=owner.id, question=q, model_a="claude", model_b="chatgpt"))
            db.add(SavedAnswer(id=f"sa-{owner.email[0]}", user_id=owner.id, battle_id=f"bt-{owner.email[0]}",
                               question=q, final_answer="x", fighters="claude,chatgpt"))
        await db.commit()

    wrong = await client.request("DELETE", "/api/users/me", json={"password": "wrong-pass-123"})
    assert wrong.status_code == 422
    ok = await client.request("DELETE", "/api/users/me", json={"password": PW})
    assert ok.status_code == 200 and ok.json()["deleted"] is True
    assert (await client.get("/api/auth/me")).status_code == 401

    async with db_factory() as db:
        def count(model):
            return db.scalar(select(func.count()).select_from(model))

        assert await count(User) == 1
        assert await count(Profile) == 1
        assert await count(Battle) == 1 and await count(SavedAnswer) == 1
        assert await count(UserSession) == 1  # only Bob's
    assert (await client_b.get("/api/users/me/profile")).status_code == 200  # Bob unaffected
    # the deleted account can no longer log in
    gone = await client.post("/api/auth/login", json={"email": "a@example.com", "password": PW})
    assert gone.status_code == 401


# ------------------------- email change & occupation -------------------------

async def test_occupation_editable_via_profile(client):
    await register(client)
    r = await client.put("/api/users/me/profile", json={"occupation": "Designer"})
    assert r.status_code == 200 and r.json()["occupation"] == "Designer"


async def test_email_change_requires_password_and_confirmation(client, client_b, outbox):
    await register(client)
    await client_b.post("/api/auth/login", json={"email": "ada@example.com", "password": PW})
    bad = await client.post("/api/auth/change-email", json={"newEmail": "new@example.com", "password": "wrong-pass-1"})
    assert bad.status_code == 422 and outbox.messages[-1]["to"] == "ada@example.com"

    ok = await client.post("/api/auth/change-email", json={"newEmail": "New@Example.com", "password": PW})
    assert ok.status_code == 200
    assert outbox.messages[-1]["to"] == "new@example.com"  # code goes to the NEW address
    # Email is unchanged until confirmed.
    assert (await client.get("/api/auth/me")).json()["email"] == "ada@example.com"

    wrong = await client.post("/api/auth/confirm-email-change", json={"code": "000000"})
    assert wrong.status_code == 422
    done = await client.post("/api/auth/confirm-email-change", json={"code": outbox.last_code()})
    assert done.status_code == 200 and done.json()["email"] == "new@example.com"

    me = (await client.get("/api/auth/me")).json()
    assert me["email"] == "new@example.com" and me["is_verified"] is True
    assert outbox.messages[-1]["to"] == "ada@example.com"  # old address is notified
    assert (await client_b.get("/api/auth/me")).status_code == 401  # other devices signed out
    # login works with the new email only
    client.cookies.clear()
    assert (await client.post("/api/auth/login", json={"email": "new@example.com", "password": PW})).status_code == 200
    assert (await client.post("/api/auth/login", json={"email": "ada@example.com", "password": PW})).status_code == 401


async def test_email_change_rejects_taken_and_same_email(client, client_b):
    await register(client, email="a@example.com")
    await register(client_b, email="b@example.com", name="Bob B")
    taken = await client.post("/api/auth/change-email", json={"newEmail": "B@example.com", "password": PW})
    assert taken.status_code == 409
    same = await client.post("/api/auth/change-email", json={"newEmail": "a@example.com", "password": PW})
    assert same.status_code == 422


async def test_email_change_code_attempt_limit_and_isolation(client, client_b, outbox):
    await register(client, email="a@example.com")
    await register(client_b, email="b@example.com", name="Bob B")
    await client.post("/api/auth/change-email", json={"newEmail": "a2@example.com", "password": PW})
    code = outbox.last_code()
    # Bob has no pending change, so Alice's code is useless to him.
    assert (await client_b.post("/api/auth/confirm-email-change", json={"code": code})).status_code == 422
    for _ in range(5):
        assert (await client.post("/api/auth/confirm-email-change", json={"code": "000000"})).status_code == 422
    assert (await client.post("/api/auth/confirm-email-change", json={"code": code})).status_code == 422
    assert (await client.get("/api/auth/me")).json()["email"] == "a@example.com"
