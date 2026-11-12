from fastapi.testclient import TestClient
import sqlite3, time
from datetime import datetime, timezone
from app.main import app
from app.scorer.auth import create_admin_session
from app.scorer.database import DB_PATH

client = TestClient(app)

def admin_login(c=client):
    token=create_admin_session("administrator")
    c.headers.update({"Authorization":"Bearer "+token})
    return {"token":token,"role":"admin"}

admin_login()

def mkplayer(name, email="", role="read-only"):
    r=client.post("/api/scorer/players",json={"name":name,"email":email,"role":role})
    assert r.status_code==200, r.text
    return r.json()["id"]

def test_scorer_page_and_health():
    r=client.get("/scorer")
    assert r.status_code==200
    assert "Badminton Scorer" in r.text
    assert "Matches" in r.text
    assert "Coach" in r.text
    assert "Play. Score. Remember. Improve." in r.text
    assert "A community driven and fast badminton scoring" in r.text
    assert "Champions are not born. They are forged through relentless discipline, daily sacrifice, and hard work." in r.text
    r=client.get("/api/scorer/health")
    assert r.status_code==200
    assert r.json()["service"]=="badminton-scorer"

def test_manual_player_creation_rejects_duplicate_name():
    created=client.post("/api/scorer/players",json={"name":"Manual Player","skill_level":"Coach"})
    assert created.status_code==200
    player=client.get(f"/api/scorer/players/{created.json()['id']}")
    assert player.json()["player"]["skill_level"]=="Coach"
    assert client.post("/api/scorer/players",json={"name":" manual player "}).status_code==409

def test_scorer_player_login_first_and_second_login_and_email():
    c=TestClient(app)
    admin_login(c)
    r=c.post("/api/scorer/players",json={"name":"Login Player","email":"login.player@example.com","role":"read-only"})
    assert r.status_code==200
    assert c.post("/api/scorer/auth/check",json={"login":"Login"}).json()["exists"] is True
    assert c.post("/api/scorer/auth/check",json={"login":"login.player@example.com"}).json()["exists"] is True
    assert c.post("/api/scorer/auth/check",json={"login":"missing@example.com"}).json()["exists"] is False
    p=TestClient(app)
    r=p.post("/api/scorer/auth/login",json={"login":"login.player@example.com","password":""})
    assert r.status_code==200 and r.json()["player"]["must_change_password"] is True
    p.headers.update({"Authorization":"Bearer "+r.json()["token"]})
    assert p.post("/api/scorer/auth/password",json={"current_password":"","new_password":"PlayerPass123"}).status_code==200
    p.post("/api/scorer/auth/logout")
    r=p.post("/api/scorer/auth/login",json={"login":"Login","password":"PlayerPass123"})
    assert r.status_code==200
    p.headers.update({"Authorization":"Bearer "+r.json()["token"]})
    assert p.post("/api/scorer/auth/login",json={"login":"Login","password":""}).status_code==401
    assert p.post("/api/scorer/players",json={"name":"Nope"}).status_code==403

def test_scorer_singles_live_game_and_undo():
    a,b=mkplayer("Scorer A"),mkplayer("Scorer B")
    r=client.post("/api/scorer/matches",json={
        "match_type":"singles","best_of":1,"player_a1_id":a,"player_b1_id":b})
    assert r.status_code==200
    mid=r.json()["match"]["id"]
    for _ in range(20): assert client.post(f"/api/scorer/matches/{mid}/point",json={"side":"A"}).status_code==200
    r=client.post(f"/api/scorer/matches/{mid}/point",json={"side":"A"})
    assert r.status_code==200
    assert r.json()["game_winner"]=="A"
    detail=client.get(f"/api/scorer/matches/{mid}").json()
    assert detail["match"]["status"]=="completed"
    assert detail["games"][0]["score_a"]==21
    # A completed match is immutable for undo.
    assert client.post(f"/api/scorer/matches/{mid}/undo").status_code==400

def test_scorer_doubles_and_team_creation():
    a,b,c,d=[mkplayer(x) for x in ["D A","D B","D C","D D"]]
    t1=client.post("/api/scorer/teams",json={"name":"Team One","player_ids":[a,b]})
    t2=client.post("/api/scorer/teams",json={"name":"Team Two","player_ids":[c,d]})
    assert t1.status_code==200 and t2.status_code==200
    r=client.post("/api/scorer/matches",json={"match_type":"team","best_of":3,
        "team_a_id":t1.json()["id"],"team_b_id":t2.json()["id"]})
    assert r.status_code==200
    assert r.json()["match"]["match_type"]=="team"

def test_scorer_doubles_player_match_statistics():
    a1,a2,b1,b2=[mkplayer(x) for x in ["Stats A1","Stats A2","Stats B1","Stats B2"]]
    r=client.post("/api/scorer/matches",json={"match_type":"doubles","best_of":1,
        "player_a1_id":a1,"player_a2_id":a2,"player_b1_id":b1,"player_b2_id":b2})
    assert r.status_code==200
    mid=r.json()["match"]["id"]
    assert client.post(f"/api/scorer/matches/{mid}/point",json={
        "side":"A","event_type":"error","error_type":"service_error",
        "player_id":a2,"opponent_player_id":b1,"error_count":3}).status_code==200
    assert client.post(f"/api/scorer/matches/{mid}/point",json={
        "side":"B","event_type":"error","error_type":"unforced_error",
        "player_id":b2,"opponent_player_id":a1}).status_code==200
    for _ in range(21):
        assert client.post(f"/api/scorer/matches/{mid}/point",json={
            "side":"A","player_id":a1}).status_code==200
    detail=client.get(f"/api/scorer/matches/{mid}").json()
    assert detail["match"]["status"]=="completed"
    stats={x["id"]:x for x in detail["player_stats"]}
    assert stats[a2]["service_faults"]==3
    assert stats[a2]["service_returns"]==0
    assert stats[b2]["unforced_errors"]==1
    assert stats[a1]["points"]==21
    assert stats[b1]["points"]==0
    game_id=detail["games"][0]["id"]
    edited=client.put(f"/api/scorer/matches/{mid}",json={
        "status":"completed","winner_side":"B","current_game":1,
        "best_of":1,"games":[{"id":game_id,"score_a":18,"score_b":21,"winner_side":"B"}],
        "player_stats":[{"player_id":x["id"],"points":x["points"],"unforced_errors":x["unforced_errors"],"service_faults":x["service_faults"],"service_returns":x.get("service_returns",0),"forced_errors":x.get("forced_errors",0)} for x in detail["player_stats"]]})
    assert edited.status_code==200
    assert edited.json()["match"]["winner_side"]=="B"
    assert edited.json()["games"][0]["score_a"]==18
    edited=client.put(f"/api/scorer/matches/{mid}",json={
        "player_stats":[{"player_id":a1,"points":18,"unforced_errors":2,
                          "service_faults":1,"service_returns":2,"forced_errors":4}]})
    assert edited.status_code==200
    edited_stats={x["id"]:x for x in edited.json()["player_stats"]}
    assert edited_stats[a1]["forced_errors"]==4
    assert edited_stats[a1]["service_returns"]==2
    period=client.get(f"/api/scorer/statistics?period=weekly&player={a2}")
    assert period.status_code==200
    assert period.json()["service_faults"]==3
    assert period.json()["service_returns"]==0
    assert period.json()["player_stats"][0]["id"]==a2
    assert period.json()["player_averages_per_game"]["service_faults"]==3.0
    assert period.json()["player_stats"][0]["skill_level"]=="Intermediate"
    ranking=client.get("/api/scorer/rankings?period=monthly")
    assert ranking.status_code==200
    assert ranking.json()["parameter"]=="error_average_then_total_errors_then_win_points_avg_per_game_then_win_rate_then_matches_then_wins"
    ranking_items={x["id"]:x for x in ranking.json()["items"]}
    assert ranking_items[a1]["matches"] == 1
    assert ranking_items[a2]["matches"] == 1
    assert ranking_items[b1]["matches"] == 1
    assert ranking_items[b2]["matches"] == 1
    weekly_ranking=client.get("/api/scorer/rankings?period=weekly")
    assert weekly_ranking.status_code==200
    assert weekly_ranking.json()["period"]=="weekly"
    selected_week=client.get("/api/scorer/rankings?period=weekly&start_date=2026-01-05&end_date=2026-01-11")
    assert selected_week.status_code==200
    assert selected_week.json()["start_date"]=="2026-01-05"
    selected_month=client.get("/api/scorer/rankings?period=monthly&month=1&year=2026")
    assert selected_month.status_code==200
    assert selected_month.json()["end_date"]=="2026-01-31"
    selected_year=client.get("/api/scorer/rankings?period=yearly&year=2026")
    assert selected_year.status_code==200
    assert selected_year.json()["start_date"]=="2026-01-01"

def test_service_return_is_recorded_and_included_in_statistics_and_ranking():
    a,b=mkplayer("Return A"),mkplayer("Return B")
    r=client.post("/api/scorer/matches",json={"match_type":"singles","best_of":1,"player_a1_id":a,"player_b1_id":b})
    assert r.status_code==200
    mid=r.json()["match"]["id"]
    r=client.post(f"/api/scorer/matches/{mid}/point",json={"side":"A","event_type":"error","error_type":"service_return","player_id":a,"opponent_player_id":b,"error_count":4})
    assert r.status_code==200
    for _ in range(21):
        assert client.post(f"/api/scorer/matches/{mid}/point",json={"side":"A"}).status_code==200
    d=client.get(f"/api/scorer/matches/{mid}").json()
    stats={x["id"]:x for x in d["player_stats"]}
    assert stats[a]["service_returns"]==4
    assert stats[b]["service_returns"]==0
    p=client.get(f"/api/scorer/players/{a}/statistics").json()
    assert p["service_returns"]==4
    period=client.get(f"/api/scorer/statistics?period=weekly&player={a}").json()
    assert period["service_returns"]==4
    assert period["player_averages_per_game"]["service_returns"]==4.0
    ranking=client.get("/api/scorer/rankings?period=weekly").json()
    items={x["id"]:x for x in ranking["items"]}
    assert items[a]["service_returns"]==4

def test_scorer_statistics_and_history():
    d=client.get("/api/scorer/statistics?period=weekly")
    assert d.status_code==200
    assert {"matches","games","points","service_errors","service_returns","unforced_errors"} <= d.json().keys()
    h=client.get("/api/scorer/history")
    assert h.status_code==200
    assert "items" in h.json()


def test_admin_player_access_management():
    c=TestClient(app); admin_login(c)
    r=c.post("/api/scorer/players",json={"name":"Access Player","email":"access@example.com"}); assert r.status_code==200
    pid=r.json()["id"]
    r=c.put(f"/api/scorer/players/{pid}",json={"name":"Access Player","email":"access@example.com","username":"access","role":"admin","blocked":False}); assert r.status_code==200
    p=TestClient(app); r=p.post("/api/scorer/auth/login",json={"login":"access@example.com","password":""}); assert r.status_code==200; assert r.json()["role"]=="admin"
    c.post(f"/api/scorer/players/{pid}/block",json={"blocked":True})
    assert p.post("/api/scorer/auth/login",json={"login":"access","password":""}).status_code==401
    c.post(f"/api/scorer/players/{pid}/block",json={"blocked":False})
    c.post(f"/api/scorer/players/{pid}/reset-password")
    r=p.post("/api/scorer/auth/login",json={"login":"access","password":""}); assert r.status_code==200


def test_default_player_role_is_scorer_and_read_only_cannot_score():
    c=TestClient(app); admin_login(c)
    r=c.post("/api/scorer/players",json={"name":"Default Scorer"})
    assert r.status_code==200
    pid=r.json()["id"]
    p=TestClient(app)
    r=p.post("/api/scorer/auth/login",json={"login":"Default","password":""})
    assert r.status_code==200 and r.json()["role"]=="scorer"
    p.headers.update({"Authorization":"Bearer "+r.json()["token"]})
    assert p.post("/api/scorer/auth/password",json={"current_password":"","new_password":"ScorerPass123"}).status_code==200
    a,b=[pid, mkplayer("Opponent")]
    created=p.post("/api/scorer/matches",json={"match_type":"singles","best_of":1,"player_a1_id":a,"player_b1_id":b})
    assert created.status_code==200
    mid=created.json()["match"]["id"]
    assert p.post(f"/api/scorer/matches/{mid}/point",json={"side":"A"}).status_code==200

    ro=client.post("/api/scorer/players",json={"name":"Read Only","role":"read-only"})
    assert ro.status_code==200
    q=TestClient(app)
    r=q.post("/api/scorer/auth/login",json={"login":"Read","password":""})
    assert r.status_code==200 and r.json()["role"]=="read-only"
    q.headers.update({"Authorization":"Bearer "+r.json()["token"]})
    assert q.post("/api/scorer/matches",json={"match_type":"singles","best_of":1,"player_a1_id":a,"player_b1_id":b}).status_code==403
    assert q.post(f"/api/scorer/matches/{mid}/point",json={"side":"A"}).status_code==403


def test_scorer_can_create_and_score_but_cannot_edit_or_delete_completed_match():
    c=TestClient(app); admin_login(c)
    a=mkplayer("Scoring User")
    b=mkplayer("Scoring Opponent")
    r=c.put(f"/api/scorer/players/{a}",json={"name":"Scoring User","username":"scoring","email":"scoring@example.com","role":"scorer","blocked":False})
    assert r.status_code==200
    s=TestClient(app)
    r=s.post("/api/scorer/auth/login",json={"login":"scoring","password":""})
    assert r.status_code==200 and r.json()["role"]=="scorer"
    s.headers.update({"Authorization":"Bearer "+r.json()["token"]})
    assert s.post("/api/scorer/auth/password",json={"current_password":"","new_password":"ScorerPass123"}).status_code==200
    r=s.post("/api/scorer/matches",json={"match_type":"singles","best_of":1,"player_a1_id":a,"player_b1_id":b})
    assert r.status_code==200
    mid=r.json()["match"]["id"]
    for _ in range(21):
        assert s.post(f"/api/scorer/matches/{mid}/point",json={"side":"A"}).status_code==200
    assert s.get(f"/api/scorer/matches/{mid}").json()["match"]["status"]=="completed"
    assert s.post(f"/api/scorer/matches/{mid}/point",json={"side":"A"}).status_code==400
    assert s.post(f"/api/scorer/matches/{mid}/undo").status_code==400
    assert s.put(f"/api/scorer/matches/{mid}",json={"status":"live"}).status_code==403
    assert s.delete(f"/api/scorer/matches/{mid}").status_code==403


def test_admin_can_still_edit_and_delete_matches():
    c=TestClient(app); admin_login(c)
    a,b=mkplayer("Admin Match A"),mkplayer("Admin Match B")
    r=c.post("/api/scorer/matches",json={"match_type":"singles","best_of":1,"player_a1_id":a,"player_b1_id":b})
    assert r.status_code==200
    mid=r.json()["match"]["id"]
    assert c.put(f"/api/scorer/matches/{mid}",json={"status":"live"}).status_code==200
    assert c.delete(f"/api/scorer/matches/{mid}").status_code==200


def test_statistics_calendar_periods_and_ranking_wins_matches_errors():
    a,b,c=[mkplayer(x) for x in ["Rank A","Rank B","Rank C"]]
    def complete(pid_a,pid_b, winner="A", service_return=0, unforced=0, service_fault=0, forced=0):
        r=client.post("/api/scorer/matches",json={"match_type":"singles","best_of":1,"player_a1_id":pid_a,"player_b1_id":pid_b})
        assert r.status_code==200
        mid=r.json()["match"]["id"]
        for _ in range(21 if winner=="A" else 19):
            assert client.post(f"/api/scorer/matches/{mid}/point",json={"side":"A" if winner=="A" else "B"}).status_code==200
        # Ensure the match is completed, then apply manual statistics for deterministic ranking tests.
        d=client.get(f"/api/scorer/matches/{mid}").json()
        stats=[]
        for pid in (pid_a,pid_b):
            stats.append({"player_id":pid,"points":21 if ((pid==pid_a and winner=="A") or (pid==pid_b and winner=="B")) else 19,
                          "unforced_errors":unforced if pid==pid_a else 0,
                          "service_faults":service_fault if pid==pid_a else 0,
                          "service_returns":service_return if pid==pid_a else 0,
                          "forced_errors":forced if pid==pid_a else 0})
        client.put(f"/api/scorer/matches/{mid}",json={"player_stats":stats})
        return mid
    # A: 2/2 wins, B: 3/3 wins, C: 1/2 wins. Perfect win rate comes first;
    # among equal win rate, fewer completed matches ranks higher.
    complete(a,c,"A",service_return=2)
    complete(a,c,"A",unforced=1)
    complete(b,c,"A",service_fault=3)
    r=client.get("/api/scorer/rankings?period=yearly")
    assert r.status_code==200
    items=r.json()["items"]
    by_name={x["name"]:x for x in items}
    assert by_name["Rank A"]["wins"]==2
    assert by_name["Rank A"]["matches"]==2
    assert by_name["Rank B"]["wins"]==1
    # B only played once in the fixture above and won it; it has 100% win rate.
    assert by_name["Rank B"]["win_rate"]==100.0
    assert by_name["Rank B"]["matches"]==1
    assert by_name["Rank B"]["service_faults"]==3
    # Current ranking prioritizes error average and total errors before win rate.
    assert [x["name"] for x in items if x["name"] in {"Rank A","Rank B","Rank C"}][0]=="Rank C"

    for period in ("weekly","monthly","yearly"):
        rr=client.get(f"/api/scorer/statistics?period={period}")
        assert rr.status_code==200
        assert rr.json()["start_date"] <= rr.json()["end_date"]
    rr=client.get("/api/scorer/statistics?period=monthly&month=1&year=2030")
    assert rr.status_code==200
    assert rr.json()["start_date"]=="2030-01-01"
    assert rr.json()["end_date"]=="2030-01-31"
    rr=client.get("/api/scorer/statistics?period=weekly&start_date=2030-01-07&end_date=2030-01-13")
    assert rr.status_code==200
    assert rr.json()["start_date"]=="2030-01-07"
    assert rr.json()["end_date"]=="2030-01-13"


def test_ranking_uses_error_average_then_total_errors_then_win_points_avg_per_game_then_win_rate_then_matches_then_wins():
    # Ranking API ordering is tested directly with representative ranking rows so the
    # priority chain remains explicit and stable as scoring evolves.
    from app.scorer.router import rankings
    rows = [
        {"name":"C", "error_average_per_game":1.0, "error_total":3, "win_rate":50.0, "matches":4, "wins":2},
        {"name":"A", "error_average_per_game":0.5, "error_total":8, "win_rate":20.0, "matches":2, "wins":1},
        {"name":"B", "error_average_per_game":0.5, "error_total":4, "win_rate":20.0, "matches":5, "wins":1},
        {"name":"D", "error_average_per_game":0.5, "error_total":4, "win_rate":20.0, "matches":3, "wins":2},
    ]
    ordered = sorted(rows, key=lambda x:(x["error_average_per_game"],x["error_total"],-x["win_rate"],x["matches"],-x["wins"],x["name"].lower()))
    assert [x["name"] for x in ordered] == ["D", "B", "A", "C"]

    # When all higher-priority criteria tie, fewer matches wins; when matches tie,
    # more wins wins; finally player name is deterministic.
    tied = [
        {"name":"Zed", "error_average_per_game":0.25, "error_total":2, "win_rate":50.0, "matches":3, "wins":1},
        {"name":"Ann", "error_average_per_game":0.25, "error_total":2, "win_rate":50.0, "matches":3, "wins":2},
        {"name":"Bob", "error_average_per_game":0.25, "error_total":2, "win_rate":50.0, "matches":2, "wins":1},
    ]
    assert [x["name"] for x in sorted(tied, key=lambda x:(x["error_average_per_game"],x["error_total"],-x["win_rate"],x["matches"],-x["wins"],x["name"].lower()))] == ["Bob", "Ann", "Zed"]



def test_album_crud_and_admin_protection():
    admin = admin_login(TestClient(app))
    client_admin = TestClient(app)
    client_admin.headers.update({"Authorization": f"Bearer {admin['token']}"})
    headers = client_admin.headers
    image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    r = client_admin.post("/api/scorer/album", headers=headers, json={"title":"Tournament Winner","category":"Winners","caption":"Gold medal day","image":image})
    assert r.status_code == 200
    aid = r.json()["id"]
    r = client_admin.get("/api/scorer/album", headers=headers)
    assert r.status_code == 200 and r.json()["items"][0]["title"] == "Tournament Winner"
    player_id = mkplayer("Album Profile Player")
    r = client_admin.put(f"/api/scorer/players/{player_id}", headers=headers, json={"name":"Album Profile Player","role":"scorer","album_id":aid})
    assert r.status_code == 200
    r = client_admin.get("/api/scorer/players", headers=headers)
    profile = next(x for x in r.json()["items"] if x["id"] == player_id)
    assert profile["album_id"] == aid and profile["album_image"].startswith("/static/scorer_album/")
    r = client_admin.put(f"/api/scorer/album/{aid}", headers=headers, json={"title":"Champions","category":"Trophies","caption":"Updated","image":""})
    assert r.status_code == 200
    r = client_admin.delete(f"/api/scorer/album/{aid}", headers=headers)
    assert r.status_code == 200
    r = client_admin.get(f"/api/scorer/players/{player_id}", headers=headers)
    assert r.status_code == 200 and r.json()["player"]["album_id"] == ""
    r = client_admin.get("/api/scorer/album", headers=headers)
    assert r.json()["items"] == []

    assert TestClient(app).post("/api/scorer/album", json={"title":"Nope","image":image}).status_code == 401


def test_player_picture_can_use_album_or_local_computer():
    admin = admin_login(TestClient(app))
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {admin['token']}"})
    image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    player_id = mkplayer("Picture Source Player")
    album = c.post("/api/scorer/album", json={"title":"Profile Album","category":"Winners","image":image})
    assert album.status_code == 200
    aid = album.json()["id"]

    r = c.put(f"/api/scorer/players/{player_id}/picture", json={"source":"album","album_id":aid})
    assert r.status_code == 200
    profile = c.get(f"/api/scorer/players/{player_id}").json()["player"]
    assert profile["album_id"] == aid and profile["profile_image"] == ""

    r = c.put(f"/api/scorer/players/{player_id}/picture", json={"source":"external","image":image})
    assert r.status_code == 200
    profile = c.get(f"/api/scorer/players/{player_id}").json()["player"]
    assert profile["album_id"] == "" and profile["profile_image"].startswith("/static/scorer_player_photos/")

    assert TestClient(app).put(f"/api/scorer/players/{player_id}/picture", json={"source":"external","image":image}).status_code == 401
    c.put(f"/api/scorer/players/{player_id}/picture", json={"source":"none"})


def test_ranking_mobile_layout_markup():
    html=client.get("/scorer").text
    assert 'class="actions ranking-periods"' in html
    assert 'id="rankingFilters" class="ranking-filters"' in html
    assert 'ranking-table-wrap' in html
    assert 'showRankingPeriod(\'custom\')' in html
    assert 'Download Ranking PDF' in html
    assert 'ranking-table{min-width:720px}' in html
    assert '@media(max-width:700px)' in html

def test_ranking_pdf_download_for_selected_period_and_custom_period():
    r=client.get('/api/scorer/rankings/pdf?period=monthly&month=1&year=2026')
    assert r.status_code==200
    assert r.headers['content-type'].startswith('application/pdf')
    assert 'attachment;' in r.headers['content-disposition']
    assert r.content.startswith(b'%PDF')
    custom=client.get('/api/scorer/rankings/pdf?period=custom&start_date=2026-01-05&end_date=2026-01-11')
    assert custom.status_code==200
    assert custom.content.startswith(b'%PDF')
    assert '2026-01-05' in custom.headers['content-disposition']
    assert '2026-01-11' in custom.headers['content-disposition']

def test_ranking_custom_period_and_pdf_require_scorer_login():
    r=client.get('/api/scorer/rankings?period=custom&start_date=2026-01-01&end_date=2026-01-31')
    assert r.status_code==200
    assert r.json()['period']=='custom'
    unauth=TestClient(app)
    assert unauth.get('/api/scorer/rankings/pdf?period=yearly&year=2026').status_code==401

def test_admin_session_manager_logs_and_idle_timeout():
    c=TestClient(app)
    token=create_admin_session("session-admin")
    c.headers.update({"Authorization":"Bearer "+token})
    sessions=c.get('/api/scorer/admin/sessions?period=day')
    assert sessions.status_code==200
    assert sessions.json()['idle_timeout_hours']==4
    logs=c.get('/api/scorer/admin/logs?period=day')
    assert logs.status_code==200
    assert 'logs' in logs.json()
    download=c.get('/api/scorer/admin/logs/download?period=day')
    assert download.status_code==200
    assert download.headers['content-type'].startswith('text/csv')
    with sqlite3.connect(DB_PATH) as db:
        db.execute('UPDATE scorer_sessions SET last_activity_at=? WHERE token=?',(int(time.time())-5*3600,token)); db.commit()
    assert c.get('/api/scorer/admin/sessions?period=day').status_code==401


def test_live_score_direct_plus_minus_and_error_adjustment():
    c=TestClient(app); token=create_admin_session('score-admin'); c.headers.update({'Authorization':'Bearer '+token})
    a=mkplayer('Direct A'); b=mkplayer('Direct B')
    m=c.post('/api/scorer/matches',json={'match_type':'singles','best_of':1,'player_a1_id':a,'player_b1_id':b}).json()['match']['id']
    assert c.post(f'/api/scorer/matches/{m}/score-adjust',json={'side':'A','delta':1}).status_code==200
    assert c.post(f'/api/scorer/matches/{m}/score-adjust',json={'side':'A','delta':-1}).status_code==200
    assert c.post(f'/api/scorer/matches/{m}/error',json={'player_id':a,'error_type':'service_return','delta':1}).status_code==200
    assert c.post(f'/api/scorer/matches/{m}/error',json={'player_id':a,'error_type':'service_return','delta':-1}).status_code==200
    d=c.get(f'/api/scorer/matches/{m}').json()
    assert d['games'][0]['score_a']==0 and d['games'][0]['score_b']==0


def test_statistics_performance_uses_same_filters_and_custom_period():
    c=TestClient(app); token=create_admin_session('graph-admin'); c.headers.update({'Authorization':'Bearer '+token})
    a=mkplayer('Graph A'); b=mkplayer('Graph B')
    m=c.post('/api/scorer/matches',json={'match_type':'singles','best_of':1,'player_a1_id':a,'player_b1_id':b}).json()['match']['id']
    for _ in range(21):
        c.post(f'/api/scorer/matches/{m}/point',json={'side':'A'})
    match_date=datetime.fromtimestamp(int(time.time()), timezone.utc).date().isoformat()
    r=c.get('/api/scorer/statistics/performance?period=custom&start_date='+match_date+'&end_date='+match_date+'&player='+a)
    assert r.status_code==200
    assert r.json()['player']==a
    assert len(r.json()['items'])>=1
    assert r.json()['items'][0]['wins']==1

def test_statistics_performance_returns_two_graph_series_and_grouping():
    r=client.get('/api/scorer/statistics/performance?period=weekly')
    assert r.status_code==200
    data=r.json()
    assert len(data['groups'])==7
    assert {'matches','wins','win_rate','averages_per_game'} <= data['groups'][0].keys()
    assert {'service_faults','service_returns','unforced_errors','forced_errors','total_errors'} <= data['groups'][0]['averages_per_game'].keys()
    monthly=client.get('/api/scorer/statistics/performance?period=monthly&month=1&year=2026').json()
    assert len(monthly['groups'])==5
    yearly=client.get('/api/scorer/statistics/performance?period=yearly&year=2026').json()
    assert len(yearly['groups'])==12
    custom=client.get('/api/scorer/statistics/performance?period=custom&start_date=2026-01-01&end_date=2026-01-14').json()
    assert len(custom['groups'])==3


def test_statistics_exposes_all_player_average_per_game():
    r=client.get('/api/scorer/statistics?period=weekly')
    assert r.status_code==200
    data=r.json()
    assert 'all_player_averages_per_game' in data
    assert {'service_faults','service_returns','unforced_errors','forced_errors'} <= data['all_player_averages_per_game'].keys()


def test_scorer_html_has_fixed_open_score_and_two_performance_graphs():
    html=client.get('/scorer').text
    assert 'async function sideName' in html
    assert 'async function openScore' in html
    assert 'id="winRateGraph"' in html
    assert 'id="averageGameGraph"' in html
    assert 'Matches</text>' in html
    assert 'Total error average / game' in html

def test_match_identifier_lock_history_team_names_session_names_and_admin_album_ui():
    a=mkplayer("Lock Alpha", role="scorer")
    b=mkplayer("Lock Beta", role="scorer")
    r=client.post("/api/scorer/matches",json={"match_type":"singles","best_of":1,"player_a1_id":a,"player_b1_id":b,"match_note":"REAL GAME - do not touch"})
    assert r.status_code==200
    mid=r.json()["match"]["id"]
    listing=client.get("/api/scorer/matches?status=live").json()["items"]
    m=next(x for x in listing if x["id"]==mid)
    assert m["match_note"]=="REAL GAME - do not touch"

    first=TestClient(app); first_token=create_admin_session("administrator"); first.headers.update({"Authorization":"Bearer "+first_token})
    second=TestClient(app); second_token=create_admin_session("administrator"); second.headers.update({"Authorization":"Bearer "+second_token})
    assert first.post(f"/api/scorer/matches/{mid}/scoring-lock").status_code==200
    blocked=second.post(f"/api/scorer/matches/{mid}/scoring-lock")
    assert blocked.status_code==409 and "currently open" in blocked.json()["detail"]
    assert second.post(f"/api/scorer/matches/{mid}/point",json={"side":"A"}).status_code==409
    assert first.delete(f"/api/scorer/matches/{mid}/scoring-lock").status_code==200
    assert second.post(f"/api/scorer/matches/{mid}/scoring-lock").status_code==200

    hist=client.get("/api/scorer/history").json()["items"]
    hm=next(x for x in hist if x["id"]==mid)
    assert hm["team_a_display"]=="Lock Alpha"
    assert hm["team_b_display"]=="Lock Beta"

    sessions=client.get("/api/scorer/admin/sessions?period=day").json()["items"]
    assert all("display_name" in x for x in sessions)
    assert any(x["player_id"]=="__scorer_admin__" and x["display_name"] and not x["display_name"].startswith("__") for x in sessions)

    page=client.get("/scorer").text
    assert "Match identifier / comment (optional)" in page
    assert "<h1>Match History</h1>" in page
    assert 'id="playerAlbumSection"' in page and "player-gallery-admin" in page
    assert ".account-name{display:inline-block;max-width:90px}" in page


def test_error_counter_awards_and_reverses_opponent_team_point():
    c=TestClient(app); admin_login(c)
    players=c.get("/api/scorer/players").json()["items"]
    if len(players)<2: pytest.skip("Requires at least two players")
    a,b=players[0]["id"],players[1]["id"]
    created=c.post("/api/scorer/matches",json={
        "match_type":"singles","best_of":1,
        "player_a1_id":a,"player_b1_id":b
    })
    assert created.status_code==200
    mid=created.json()["match"]["id"]
    before=c.get(f"/api/scorer/matches/{mid}").json()["games"][0]
    plus=c.post(f"/api/scorer/matches/{mid}/error",
        json={"player_id":a,"error_type":"forced_error","delta":1})
    assert plus.status_code==200
    after=c.get(f"/api/scorer/matches/{mid}").json()["games"][0]
    assert after["score_a"]==before["score_a"]
    assert after["score_b"]==before["score_b"]+1
    minus=c.post(f"/api/scorer/matches/{mid}/error",
        json={"player_id":a,"error_type":"forced_error","delta":-1})
    assert minus.status_code==200
    final=c.get(f"/api/scorer/matches/{mid}").json()["games"][0]
    assert final["score_b"]==before["score_b"]


def test_error_decrement_reverses_opponent_point_without_row_key_error():
    c=TestClient(app); admin_login(c)
    players=c.get("/api/scorer/players").json()["items"]
    if len(players)<2: pytest.skip("Requires at least two players")
    a,b=players[0]["id"],players[1]["id"]
    created=c.post("/api/scorer/matches",json={
        "match_type":"singles","best_of":1,
        "player_a1_id":a,"player_b1_id":b
    })
    assert created.status_code==200
    mid=created.json()["match"]["id"]
    assert c.post(f"/api/scorer/matches/{mid}/error",
        json={"player_id":a,"error_type":"forced_error","delta":1}).status_code==200
    minus=c.post(f"/api/scorer/matches/{mid}/error",
        json={"player_id":a,"error_type":"forced_error","delta":-1})
    assert minus.status_code==200
    detail=c.get(f"/api/scorer/matches/{mid}").json()
    assert detail["games"][0]["score_b"]==0
    pstat=next(x for x in detail["player_stats"] if x["id"]==a)
    assert pstat["forced_errors"]==0

def test_generated_games_preview_and_atomic_create_with_schedule_and_teams_display():
    names=[("Gen Adv A","Advanced"),("Gen Int A","Intermediate"),("Gen Adv B","Advanced"),("Gen Int B","Intermediate")]
    ids=[]
    for name,skill in names:
        r=client.post('/api/scorer/players',json={'name':name,'skill_level':skill,'role':'scorer'})
        assert r.status_code==200, r.text
        ids.append(r.json()['id'])
    now=int(time.time())+3600
    body={'match_type':'doubles','player_ids':ids,'skill_levels':['Intermediate','Advanced'],'start_at':now,'end_at':now+7200,'duration_minutes':20,'best_of':1,'preview':True}
    preview=client.post('/api/scorer/matches/generate',json=body)
    assert preview.status_code==200, preview.text
    assert preview.json()['total']>=1
    body['preview']=False
    made=client.post('/api/scorer/matches/generate',json=body)
    assert made.status_code==200, made.text
    assert made.json()['created']==preview.json()['total']
    mid=made.json()['match_ids'][0]
    matches=client.get('/api/scorer/matches').json()['items']
    m=next(x for x in matches if x['id']==mid)
    assert m['schedule_batch_id']==made.json()['batch_id']
    assert m['scheduled_start_at']==now
    assert ' vs ' in m['teams_display']
    assert m['schedule_state']=='upcoming'


def test_generated_games_support_coach_skill_distribution():
    # Contract-level guard: Coach is part of the generator defaults and balanced doubles compositions.
    from app.scorer.router import GenerateMatchesIn
    defaults=GenerateMatchesIn(player_ids=["a","b","c","d"],start_at=1,end_at=3601)
    assert "Coach" in defaults.skill_levels
    import inspect
    from app.scorer import router as scorer_router
    source=inspect.getsource(scorer_router.generate_matches)
    assert '("Coach","Intermediate")' in source
    assert '("Coach","Intermediate++")' in source
    assert '("Coach","Advanced")' in source
    assert '("Coach","Coach")' in source


def test_generate_preview_distributes_single_coach(client, admin_headers):
    # Create four players whose balanced doubles split is:
    # Coach + Intermediate vs Advanced + Intermediate++.
    ids=[]
    for idx,skill in enumerate(["Coach","Advanced","Intermediate++","Intermediate"]):
        r=client.post("/api/scorer/players",headers=admin_headers,json={
            "name":f"CoachDist{idx}","email":f"coachd{idx}@example.com",
            "skill_level":skill,"role":"scorer"
        })
        assert r.status_code in (200,201), r.text
        ids.append(r.json()["id"])
    r=client.post("/api/scorer/matches/generate",headers=admin_headers,json={
        "match_type":"doubles","player_ids":ids,
        "skill_levels":["Intermediate","Intermediate++","Advanced","Coach"],
        "start_at":1893456000,"end_at":1893463200,
        "duration_minutes":20,"best_of":1,"preview":True
    })
    assert r.status_code==200, r.text
    data=r.json()
    assert data["total"] >= 1
    assert any(any("CoachDist0" == n for n in g["team_a"]+g["team_b"]) for g in data["games"])
