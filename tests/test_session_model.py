import session_model as sm
from session_model import Attendance


def make_session(max_main=2, max_reserve=1):
    return sm.create_session("جمعه 20:00", "زمین", max_main, max_reserve)


def ids(session, list_name):
    return [entry_id for entry_id, _ in session[list_name]]


def test_attend_fills_main_then_reserve_then_refuses():
    s = make_session()
    assert sm.attend(s, 1, "a") is Attendance.JOINED_MAIN
    assert sm.attend(s, 2, "b") is Attendance.JOINED_MAIN
    assert sm.attend(s, 3, "c") is Attendance.JOINED_RESERVE
    assert sm.attend(s, 4, "d") is Attendance.SESSION_FULL
    assert ids(s, sm.MAIN) == [1, 2] and ids(s, sm.RESERVE) == [3]


def test_attend_twice_keeps_position():
    s = make_session()
    sm.attend(s, 1, "a")
    sm.attend(s, 2, "b")
    assert sm.attend(s, 1, "a") is Attendance.UNCHANGED
    assert ids(s, sm.MAIN) == [1, 2]


def test_full_session_does_not_remove_user_from_other_lists():
    s = make_session(max_main=1, max_reserve=0)
    sm.attend(s, 1, "a")
    sm.mark_not_coming(s, 2, "b")
    assert sm.attend(s, 2, "b") is Attendance.SESSION_FULL
    assert ids(s, sm.NOT_COMING) == [2]


def test_not_coming_promotes_from_reserve_but_skips_maybe():
    s = make_session(max_main=1, max_reserve=2)
    sm.attend(s, 1, "a")
    sm.mark_maybe(s, 2, "maybe")
    sm.attend(s, 3, "c")  # reserve, waiting
    assert sm.mark_not_coming(s, 1, "a") is Attendance.MARKED_OUT
    assert ids(s, sm.MAIN) == [3]
    assert ids(s, sm.RESERVE) == [2]
    assert ids(s, sm.NOT_COMING) == [1]


def test_maybe_from_main_frees_spot_for_reserve():
    s = make_session(max_main=1, max_reserve=2)
    sm.attend(s, 1, "a")
    sm.attend(s, 2, "b")  # reserve
    assert sm.mark_maybe(s, 1, "a") is Attendance.MARKED_MAYBE
    assert ids(s, sm.MAIN) == [2]
    assert ids(s, sm.RESERVE) == [1]


def test_maybe_when_reserve_full_keeps_user_in_main():
    s = make_session(max_main=1, max_reserve=1)
    sm.attend(s, 1, "a")
    sm.attend(s, 2, "b")
    assert sm.mark_maybe(s, 1, "a") is Attendance.RESERVE_FULL
    assert ids(s, sm.MAIN) == [1]


def test_guest_add_find_remove():
    s = make_session(max_main=1, max_reserve=1)
    sm.attend(s, 1, "a")
    assert sm.add_guest(s, -100, 1, "a", "Ali") == sm.RESERVE
    guest = sm.find_guest(s, "ali")
    assert guest is not None and sm.guest_inviter(s, guest[0])["user_id"] == 1
    sm.remove_guest(s, guest[0])
    assert s[sm.RESERVE] == [] and s["guest_owners"] == {}
    assert sm.add_guest(s, -100, 1, "a", "x") == sm.RESERVE
    assert sm.add_guest(s, -100, 1, "a", "y") is None


def test_capacity_shrink_moves_and_drops():
    s = make_session(max_main=3, max_reserve=1)
    for uid in (1, 2, 3):
        sm.attend(s, uid, str(uid))
    s["max_main"], s["max_reserve"] = 1, 1
    changes = sm.apply_capacity_limits(s)
    assert ids(s, sm.MAIN) == [1]
    assert [e[0] for e in changes.moved_to_reserve] == [2]
    assert [e[0] for e in changes.dropped_from_main] == [3]


def test_capacity_growth_promotes():
    s = make_session(max_main=1, max_reserve=2)
    for uid in (1, 2, 3):
        sm.attend(s, uid, str(uid))
    s["max_main"] = 3
    changes = sm.apply_capacity_limits(s)
    assert ids(s, sm.MAIN) == [1, 2, 3]
    assert [e[0] for e in changes.promoted] == [2, 3]
