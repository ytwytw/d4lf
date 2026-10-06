from threading import Thread

from src.app.interaction import GAME_INTERACTION_LOCK


def test_hotkey_admission_allows_nested_start_but_excludes_other_thread():
    admitted = []

    def other_thread():
        acquired = GAME_INTERACTION_LOCK.acquire(blocking=False)
        admitted.append(acquired)
        if acquired:
            GAME_INTERACTION_LOCK.release()

    with GAME_INTERACTION_LOCK, GAME_INTERACTION_LOCK:
        thread = Thread(target=other_thread)
        thread.start()
        thread.join(timeout=1)
        assert not thread.is_alive()
    assert admitted == [False]
