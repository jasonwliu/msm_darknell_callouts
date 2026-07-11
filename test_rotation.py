from rotation import RotationEngine

def test_initial_state():
    engine = RotationEngine()
    assert engine.phase == 1
    assert engine.index == 0
    assert engine.get_next_moves() == ["Meteor", "Push", "Buff"]

def test_normal_advance():
    engine = RotationEngine()
    engine.advance()
    assert engine.index == 1
    assert engine.get_next_moves() == ["Push", "Buff", "Dash"]

def test_voice_command_normal():
    engine = RotationEngine()
    changed, msg = engine.process_voice_command("meteor")
    assert changed
    assert engine.index == 1
    assert engine.get_next_moves() == ["Push", "Buff", "Dash"]

def test_voice_command_skip_1():
    engine = RotationEngine()
    # next expected: Meteor, then Push
    # Let's say "push" (skips Meteor, i.e. 1 skip)
    changed, msg = engine.process_voice_command("push")
    assert changed
    assert "Stun detected" in msg
    assert engine.index == 2  # next move is Buff
    assert engine.get_next_moves() == ["Buff", "Dash", "Fly"]

def test_voice_command_skip_3():
    engine = RotationEngine()
    # next expected: Meteor, Push, Buff, Dash, Fly
    # Let's say "dash" (skips Meteor, Push, Buff - i.e. 3 skips)
    changed, msg = engine.process_voice_command("dash")
    assert changed
    assert "Stun detected" in msg
    assert engine.index == 4  # next move is Fly
    assert engine.get_next_moves()[0] == "Fly"

def test_voice_command_reset():
    engine = RotationEngine()
    engine.advance()
    engine.advance()
    changed, msg = engine.process_voice_command("reset")
    assert changed
    assert engine.index == 0

def test_voice_command_manual_phase():
    engine = RotationEngine()
    changed, msg = engine.process_voice_command("p2")
    assert changed
    assert engine.phase == 2
    assert engine.index == 0
    assert engine.get_next_moves()[0] == "Buff"

def test_voice_command_pattern_phase():
    engine = RotationEngine()
    # We are in Phase 1.
    # Phase 2 starts with Buff, Charge, Push.
    # If we say "charge", it's not in Phase 1's skip window.
    # It should transition to Phase 2, and set index to 2 (after Charge, which is Push).
    changed, msg = engine.process_voice_command("charge")
    assert changed
    assert engine.phase == 2
    assert engine.index == 2
    assert engine.get_next_moves()[0] == "Push"
    print("Pattern phase test passed:", msg)
