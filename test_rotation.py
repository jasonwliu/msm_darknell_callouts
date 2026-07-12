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
    # Let's say "stun", then "push" (skips Meteor, i.e. 1 skip)
    changed_stun, msg_stun = engine.process_voice_command("stun")
    assert changed_stun
    assert engine.stun_flag == True
    
    changed, msg = engine.process_voice_command("push")
    assert changed
    assert "Stun detected" in msg
    assert engine.stun_flag == False
    assert engine.index == 2  # next move is Buff
    assert engine.get_next_moves() == ["Buff", "Dash", "Fly"]

def test_voice_command_skip_3():
    engine = RotationEngine()
    # next expected: Meteor, Push, Buff, Dash, Fly
    # Let's say "stunned", then "dash" (skips Meteor, Push, Buff - i.e. 3 skips)
    changed_stun, msg_stun = engine.process_voice_command("stunned")
    assert changed_stun
    assert engine.stun_flag == True
    
    changed, msg = engine.process_voice_command("dash")
    assert changed
    assert "Stun detected" in msg
    assert engine.stun_flag == False
    assert engine.index == 4  # next move is Fly
    assert engine.get_next_moves()[0] == "Fly"

def test_voice_command_out_of_order_without_stun_ignored():
    engine = RotationEngine()
    # next expected: Meteor
    # speak: "push" (which is index 1, not index 0, and no stun mode)
    # it should not skip and should remain at index 0
    changed, msg = engine.process_voice_command("push")
    assert not changed
    assert engine.index == 0

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

def test_voice_command_repeat_ignore():
    engine = RotationEngine()
    # Phase 1 sequence starting: Meteor, Push, Buff, Dash, Fly, Meteor...
    # Say meteor: advances index to 1 ("Push")
    changed, msg = engine.process_voice_command("meteor")
    assert changed
    assert engine.index == 1
    
    # Say meteor again: it's in the past 3 executed moves (Index 0 is Meteor).
    # Since it's a repeat, it should be ignored.
    changed, msg = engine.process_voice_command("meteor")
    assert not changed
    assert "Ignored repeat" in msg
    assert engine.index == 1

def test_voice_command_sequence_sync():
    engine = RotationEngine()
    # speak: "buff", "push"
    changed1, msg1 = engine.process_voice_command("buff")
    assert not changed1  # Ignored as a single out-of-order move
    assert engine.index == 0  # Index remains at start
    
    changed2, msg2 = engine.process_voice_command("push")
    # "buff" then "push" uniquely matches Phase 1 index 6-7 ("Buff", "Push").
    # It should sync index to (7 + 1) = 8 ("Fly").
    assert changed2
    assert engine.index == 8
    assert "Sequence matched" in msg2

def test_voice_command_fly_into_meteor_sync():
    engine = RotationEngine()
    # Next expected is Meteor. User says "fly", then "meteor"
    changed1, msg1 = engine.process_voice_command("fly")
    assert not changed1
    assert engine.index == 0
    
    changed2, msg2 = engine.process_voice_command("meteor")
    # "fly" followed by "meteor" should match index 4-5 and sync to next index (6, "Buff")
    assert changed2
    assert engine.index == 6
    assert "Sequence matched" in msg2


